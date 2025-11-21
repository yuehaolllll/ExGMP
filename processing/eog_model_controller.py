# File: processing/model_controller.py

import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import torch
import torch.nn.functional as F
import os
import time
from scipy.signal import butter, filtfilt, iirnotch

# --- 尝试导入模型类 ---
try:
    from .rsca_model import RSCA_Net

    print("Model class imported from local package.")
except ImportError:
    try:
        from rsca_model_test import RSCA_Net

        print("Model class imported from current directory.")
    except ImportError as e:
        print(f"CRITICAL ERROR: Could not import RSCA_Net. Details: {e}")
        RSCA_Net = None

# --- 常量配置 ---
MODEL_PATH = "./models/rsca_net_8class_5_robust.pth"
CLASS_LABELS = ['up', 'down', 'left', 'right', 'blink_once', 'blink_twice', 'blink_three', 'fixation']

# 反向动作映射（用于防误触抑制）
OPPOSITE_ACTIONS = {
    'UP': 'DOWN',
    'DOWN': 'UP',
    'LEFT': 'RIGHT',
    'RIGHT': 'LEFT'
}

# --- 核心参数设置 ---
TARGET_SAMPLE_RATE = 250  # 模型训练时的采样率 (Hz)
CONFIDENCE_THRESHOLD = 0.85  # 置信度阈值
COOLDOWN_PERIOD = 0.4  # 两次预测之间的最小间隔 (秒)
REBOUND_SUPPRESSION_TIME = 0.6  # 反向动作抑制时间 (秒)

# 窗口参数
PREDICTION_WINDOW_SAMPLES = 250  # 模型需要的输入长度 (1秒 @ 250Hz)
FILTER_PADDING = 16  # 滤波边缘填充长度 (用于消除 filtfilt 边缘效应)
ENERGY_WINDOW_SAMPLES = 50  # 能量检测窗口
EVENT_TRIGGER_THRESHOLD = 20.0  # 触发预测的能量阈值
MAX_BUFFER_SIZE = 1000  # 缓冲区最大长度


class SignalProcessor:
    def __init__(self, fs=250):
        self.fs = fs
        # 1. 设计低通滤波器 (12Hz, 4阶)
        # 用于提取眼动信号包络，压制高频肌电
        self.b, self.a = butter(4, 12 / (0.5 * fs), btype='low')

        # 2. 工频陷波器 (50Hz)
        self.b_notch, self.a_notch = iirnotch(50, 30, fs)

    def apply_filter(self, data):
        """
        对数据窗口进行零相位滤波。
        data shape: (Channels, Length)
        """
        # 1. 去除工频
        data = filtfilt(self.b_notch, self.a_notch, data, axis=1)
        # 2. 低通提取 EOG
        filtered_data = filtfilt(self.b, self.a, data, axis=1)
        return filtered_data


class ModelController(QObject):
    prediction_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # 缓冲区存储的是已经降采样到 250Hz 的数据
        self.data_buffer = collections.deque(maxlen=MAX_BUFFER_SIZE)

        # 信号处理器 (固定为模型采样率 250Hz)
        self.dsp = SignalProcessor(fs=TARGET_SAMPLE_RATE)

        self.model = None
        self.device = None
        self.is_active = False

        # 采样率适配
        self.input_sample_rate = 1000  # 默认硬件采样率，会被 set_input_sample_rate 更新
        self.downsample_step = 4  # 1000 / 250 = 4

        # 状态控制
        self.threshold = CONFIDENCE_THRESHOLD
        self.last_prediction_time = 0

        # 反向抑制状态
        self.last_valid_action = None
        self.last_valid_time = 0

        # 默认通道索引 (需要 set_channel_names 更新)
        self.channel_indices = {'up': 2, 'down': 3, 'left': 0, 'right': 1}

    @pyqtSlot(list)
    def set_channel_names(self, names):
        """根据通道名称动态寻找 EOG 通道索引"""
        try:
            lower_names = [n.lower().strip() for n in names]
            # 先全部置为 -1
            for k in self.channel_indices: self.channel_indices[k] = -1

            # 简单的关键词匹配
            for i, name in enumerate(lower_names):
                if 'up' in name:
                    self.channel_indices['up'] = i
                elif 'down' in name:
                    self.channel_indices['down'] = i
                elif 'left' in name:
                    self.channel_indices['left'] = i
                elif 'right' in name:
                    self.channel_indices['right'] = i

            print(f"ModelController: EOG Indices updated: {self.channel_indices}")
        except Exception as e:
            print(f"Warning setting channel names: {e}")

    @pyqtSlot(int)
    def set_input_sample_rate(self, rate):
        """核心适配：当硬件采样率改变时，计算新的降采样步长"""
        if rate <= 0: return
        self.input_sample_rate = rate
        # 计算步长，例如 1000 / 250 = 4.0 -> 4
        # 如果硬件是 250Hz，步长为 1
        self.downsample_step = int(max(1, round(rate / TARGET_SAMPLE_RATE)))
        print(
            f"ModelController: Input fs={rate}Hz. Downsample step set to {self.downsample_step} (Target {TARGET_SAMPLE_RATE}Hz)")

    @pyqtSlot(bool)
    def set_active(self, is_active):
        if is_active and self.model is None:
            self._load_model()

        if is_active:
            self.data_buffer.clear()
            self.last_prediction_time = 0
            self.last_valid_action = None
            self.last_valid_time = 0

        self.is_active = is_active
        print(f"Model Controller active: {self.is_active}")

    @pyqtSlot(np.ndarray)
    def process_data_chunk(self, filtered_chunk):
        """
        处理输入数据块。
        Args:
            filtered_chunk: 来自 DataProcessor 的数据，已经过初步滤波，采样率为 input_sample_rate
        """
        if not self.is_active or self.model is None: return
        # 检查通道索引是否有效
        if any(v == -1 for v in self.channel_indices.values()): return

        # --- 1. 降采样适配 (Hardware Fs -> 250Hz) ---
        # 使用切片进行高效降采样
        downsampled_chunk = filtered_chunk[:, ::self.downsample_step]

        if downsampled_chunk.shape[1] == 0: return

        # --- 2. 提取 EOG 4通道 ---
        eog_chunk = downsampled_chunk[[
                                          self.channel_indices['up'],
                                          self.channel_indices['down'],
                                          self.channel_indices['left'],
                                          self.channel_indices['right']
                                      ], :]

        # --- 3. 存入缓冲区 ---
        # deque 存储转置后的数据 (N, 4) 方便 extend
        self.data_buffer.extend(eog_chunk.T)

        # --- 4. 检查冷却时间 ---
        current_time = time.time()
        if (current_time - self.last_prediction_time) > COOLDOWN_PERIOD:
            self._detect_and_classify_event()

    def _detect_and_classify_event(self):
        # 我们需要的总长度 = 模型输入长度 + 2 * 边缘填充长度
        required_samples = PREDICTION_WINDOW_SAMPLES + (2 * FILTER_PADDING)

        if len(self.data_buffer) < required_samples: return

        # 1. 能量粗筛 (只检查最近的 ENERGY_WINDOW_SAMPLES 个点)
        # 注意：这里是在降采样后的 250Hz 数据上检查
        recent_data = np.array(list(self.data_buffer)[-ENERGY_WINDOW_SAMPLES:])
        # 计算4个通道的标准差最大值
        energy = np.max(np.std(recent_data, axis=0))

        if energy > EVENT_TRIGGER_THRESHOLD:
            # 取出足够长的数据用于滤波
            # 转置为 (Channels, Length) -> (4, N)
            full_buffer_array = np.array(self.data_buffer).T

            # 截取最后 required_samples 个点
            raw_window_padded = full_buffer_array[:, -required_samples:]

            # 2. 信号滤波 (零相位低通)
            # 在较长的数据上滤波，以消除 filtfilt 的边缘效应
            clean_window_padded = self.dsp.apply_filter(raw_window_padded)

            # 3. 切除边缘，提取纯净的中间段
            # 取 [padding : -padding]，长度正好是 PREDICTION_WINDOW_SAMPLES (250)
            clean_window = clean_window_padded[:, FILTER_PADDING:-FILTER_PADDING]

            # 双重检查形状
            if clean_window.shape[1] != PREDICTION_WINDOW_SAMPLES:
                return

            # 4. 差分计算 (构建 H-EOG 和 V-EOG)
            # 索引对应: 0:up, 1:down, 2:left, 3:right
            # V_EOG = UP - DOWN
            v_eog = clean_window[0, :] - clean_window[1, :]
            # H_EOG = RIGHT - LEFT (通常定义为 Right-Left，也可能是 Left-Right，视模型训练而定)
            # 根据你的原代码: h_eog = right - left (原代码索引 3 - 2, 对应 right - left)
            h_eog = clean_window[3, :] - clean_window[2, :]

            input_signal = np.vstack([h_eog, v_eog])

            # 5. Z-Score 归一化 (逐通道)
            for ch in range(2):
                std_val = np.std(input_signal[ch, :])
                mean_val = np.mean(input_signal[ch, :])
                if std_val > 1e-6:
                    input_signal[ch, :] = (input_signal[ch, :] - mean_val) / std_val
                else:
                    input_signal[ch, :] = input_signal[ch, :] - mean_val

            # 6. 执行预测
            self._predict(input_signal)

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            print(f"Error: Model file not found at '{MODEL_PATH}'")
            return
        try:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if RSCA_Net is None: return

            self.model = RSCA_Net(in_channels=2, num_classes=len(CLASS_LABELS))
            checkpoint = torch.load(MODEL_PATH, map_location=self.device)
            self.model.load_state_dict(checkpoint)
            self.model.to(self.device)
            self.model.eval()
            print(f"Info: Loaded model successfully on {self.device}.")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None

    def _predict(self, input_signal):
        # 转为 Tensor: (1, 2, 250)
        data_tensor = torch.from_numpy(input_signal).unsqueeze(0).float().to(self.device)

        with torch.no_grad():
            outputs = self.model(data_tensor)
            probabilities = F.softmax(outputs, dim=1)
            max_prob, predicted_idx = torch.max(probabilities, 1)

            confidence = max_prob.item()
            prediction_index = predicted_idx.item()
            predicted_label = CLASS_LABELS[prediction_index]

        # 阈值过滤
        if confidence < self.threshold: return
        if predicted_label == 'fixation': return

        final_prediction = predicted_label.upper()
        current_time = time.time()

        # --- 智能反向抑制逻辑 ---

        # 1. 眨眼 = 强制重置 (通常用于确认/解锁)
        if 'BLINK' in final_prediction:
            self.last_valid_action = None
            self.last_valid_time = 0

            # 发送信号
            self.prediction_ready.emit(final_prediction)
            print(f">>> ACTION: {final_prediction} (UNLOCKING Lock)")

            # 立即清空缓冲区，防止重复触发
            self.last_prediction_time = current_time
            self.data_buffer.clear()
            return

        # 2. 检查是否为反向动作 (回弹)
        is_opposite = False
        if self.last_valid_action and self.last_valid_action not in ['BLINK_ONCE', 'BLINK_TWICE', 'BLINK_THREE']:
            expected_opposite = OPPOSITE_ACTIONS.get(self.last_valid_action)
            if expected_opposite == final_prediction:
                is_opposite = True

        # 3. 执行抑制
        if is_opposite and (current_time - self.last_valid_time) < REBOUND_SUPPRESSION_TIME:
            print(f"Ignored Rebound: {final_prediction} (Too soon after {self.last_valid_action})")
            # 即使抑制了，也建议稍微清一下缓冲，防止连续误判
            self.data_buffer.clear()
            return

        # 4. 通过验证，发送结果
        self.prediction_ready.emit(final_prediction)

        # 更新状态
        self.last_valid_action = final_prediction
        self.last_valid_time = current_time
        self.last_prediction_time = current_time

        # 预测成功后清空缓冲区，等待下一次新的眼动开始
        self.data_buffer.clear()

        print(f">>> ACTION: {final_prediction} (Conf: {confidence:.2f})")