# In processing/model_controller.py

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

# 定义反向动作映射字典
OPPOSITE_ACTIONS = {
    'UP': 'DOWN',
    'DOWN': 'UP',
    'LEFT': 'RIGHT',
    'RIGHT': 'LEFT'
}

# 参数设置
CONFIDENCE_THRESHOLD = 0.85
COOLDOWN_PERIOD = 0.4
REBOUND_SUPPRESSION_TIME = 0.6  # 回弹抑制时间

# 窗口与检测参数
PREDICTION_WINDOW_SAMPLES = 250
ENERGY_WINDOW_SAMPLES = 50
EVENT_TRIGGER_THRESHOLD = 20.0
MAX_BACKTRACE_SAMPLES = 150


class SignalProcessor:
    def __init__(self, fs=250):
        self.fs = fs
        # 1. 设计低通滤波器 (12Hz, 4阶)
        # 稍微提高到12Hz，保留更多眼动细节，同时压制肌电
        self.b, self.a = butter(4, 12 / (0.5 * fs), btype='low')

        # 2. 工频陷波器 (50Hz)
        self.b_notch, self.a_notch = iirnotch(50, 30, fs)

    def apply_filter(self, data):
        """
        对数据窗口进行滤波。
        data shape: (Channels, Length) -> (4, 250)
        """
        # 1. 去除工频干扰
        data = filtfilt(self.b_notch, self.a_notch, data, axis=1)

        # 2. 低通滤波
        # 使用 filtfilt 而不是 lfilter，实现零相位滤波
        filtered_data = filtfilt(self.b, self.a, data, axis=1)

        return filtered_data


class ModelController(QObject):
    prediction_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.data_buffer = collections.deque(maxlen=PREDICTION_WINDOW_SAMPLES + MAX_BACKTRACE_SAMPLES)

        # 信号处理器
        self.dsp = SignalProcessor(fs=250)

        self.model = None
        self.device = None
        self.is_active = False
        self.threshold = CONFIDENCE_THRESHOLD
        self.last_prediction_time = 0

        # 初始化反向抑制所需的状态变量
        self.last_valid_action = None
        self.last_valid_time = 0

        # 默认通道索引
        self.channel_indices = {'up': 2, 'down': 3, 'left': 0, 'right': 1}

    @pyqtSlot(list)
    def set_channel_names(self, names):
        try:
            lower_names = [n.lower().strip() for n in names]
            for k in self.channel_indices: self.channel_indices[k] = -1

            for i, name in enumerate(lower_names):
                if 'up' in name:
                    self.channel_indices['up'] = i
                elif 'down' in name:
                    self.channel_indices['down'] = i
                elif 'left' in name:
                    self.channel_indices['left'] = i
                elif 'right' in name:
                    self.channel_indices['right'] = i

            print(f"ModelController: Indices updated: {self.channel_indices}")
        except Exception as e:
            print(f"Warning setting channel names: {e}")

    @pyqtSlot(bool)
    def set_active(self, is_active):
        if is_active and self.model is None: self._load_model()
        if is_active:
            self.data_buffer.clear()
            self.last_prediction_time = 0
            # 重置抑制状态
            self.last_valid_action = None
            self.last_valid_time = 0
        self.is_active = is_active
        print(f"Model Controller active: {self.is_active}")

    @pyqtSlot(np.ndarray)
    def process_data_chunk(self, filtered_chunk):
        if not self.is_active or self.model is None: return
        if any(v == -1 for v in self.channel_indices.values()): return

        # 提取4通道
        eog_chunk = filtered_chunk[[self.channel_indices['up'], self.channel_indices['down'],
                                    self.channel_indices['left'], self.channel_indices['right']], :]

        # 存入缓冲区 (deque 存储 N x Channels)
        self.data_buffer.extend(eog_chunk.T)

        # 检查冷却
        current_time = time.time()
        if (current_time - self.last_prediction_time) > COOLDOWN_PERIOD:
            self._detect_and_classify_event()

    def _detect_and_classify_event(self):
        if len(self.data_buffer) < PREDICTION_WINDOW_SAMPLES: return

        # 1. 能量粗筛
        recent_data = np.array(list(self.data_buffer)[-ENERGY_WINDOW_SAMPLES:])
        energy = np.max(np.std(recent_data, axis=0))

        if energy > EVENT_TRIGGER_THRESHOLD:
            # 取出数据并转置为 (Channels, Length) 以供滤波和计算
            buffer_array = np.array(self.data_buffer).T

            if buffer_array.shape[1] >= PREDICTION_WINDOW_SAMPLES:
                raw_window = buffer_array[:, -PREDICTION_WINDOW_SAMPLES:]

                # 2. 信号滤波 (零相位低通)
                clean_window = self.dsp.apply_filter(raw_window)

                # 3. 差分计算 (H-EOG, V-EOG)
                h_eog = clean_window[3, :] - clean_window[2, :]  # Right - Left
                v_eog = clean_window[0, :] - clean_window[1, :]  # Up - Down

                input_signal = np.vstack([h_eog, v_eog])

                # 4. Z-Score 归一化
                for ch in range(2):
                    std_val = np.std(input_signal[ch, :])
                    mean_val = np.mean(input_signal[ch, :])
                    if std_val > 1e-6:
                        input_signal[ch, :] = (input_signal[ch, :] - mean_val) / std_val
                    else:
                        input_signal[ch, :] = input_signal[ch, :] - mean_val

                # 5. 预测
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
        data_tensor = torch.from_numpy(input_signal).unsqueeze(0).float().to(self.device)

        with torch.no_grad():
            outputs = self.model(data_tensor)
            probabilities = F.softmax(outputs, dim=1)
            max_prob, predicted_idx = torch.max(probabilities, 1)

            confidence = max_prob.item()
            prediction_index = predicted_idx.item()
            predicted_label = CLASS_LABELS[prediction_index]

        if confidence < self.threshold: return
        if predicted_label == 'fixation': return

        final_prediction = predicted_label.upper()
        current_time = time.time()

        # --- 智能反向抑制逻辑 ---

        # 1. 眨眼 = 强制解锁
        if 'BLINK' in final_prediction:
            self.last_valid_action = None
            self.last_valid_time = 0

            self.prediction_ready.emit(final_prediction)
            print(f">>> ACTION: {final_prediction} (UNLOCKING Lock)")

            self.last_prediction_time = current_time
            self.data_buffer.clear()
            return

        # 2. 检查反向动作
        is_opposite = False
        if self.last_valid_action and self.last_valid_action not in ['BLINK_ONCE', 'BLINK_TWICE', 'BLINK_THREE']:
            # 必须使用全局定义的 OPPOSITE_ACTIONS 字典
            expected_opposite = OPPOSITE_ACTIONS.get(self.last_valid_action)
            if expected_opposite == final_prediction:
                is_opposite = True

        # 3. 执行抑制
        if is_opposite and (current_time - self.last_valid_time) < REBOUND_SUPPRESSION_TIME:
            print(f"Ignored Rebound: {final_prediction} (Too soon after {self.last_valid_action})")
            self.data_buffer.clear()
            return

        # 4. 通过验证
        self.prediction_ready.emit(final_prediction)
        self.last_valid_action = final_prediction
        self.last_valid_time = current_time
        self.last_prediction_time = current_time
        self.data_buffer.clear()

        print(f">>> ACTION: {final_prediction} (Conf: {confidence:.2f})")