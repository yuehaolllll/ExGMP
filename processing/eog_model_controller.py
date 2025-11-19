# In processing/model_controller.py

import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import torch
import torch.nn.functional as F
import os
import time
import sys
from torch import nn


try:
    from .rsca_model import RSCA_Net
    print("Successfully imported RSCA_Net from local 'processing' directory.")

except ImportError as e:
    print(f"FATAL ERROR: Could not import RSCA_Net from './rsca_model.py'. Error: {e}")
    # 后备的假类，以防万一
    class RSCA_Net(nn.Module):
        def __init__(self,*args,**kwargs): super().__init__(); self.fc=nn.Linear(1,1)
        def forward(self,x): return torch.zeros(x.size(0), 8)

# --- 常量 ---
MODEL_PATH = "./models/rsca_net_8class_dual_channel.pth"
CLASS_LABELS = ['up', 'down', 'left', 'right', 'blink_once', 'blink_twice', 'blink_three', 'fixation']
CONFIDENCE_THRESHOLD = 0.8
COOLDOWN_PERIOD = 0.5  # 冷却时间可以稍微延长一点

# --- 窗口构成常量 ---
PREDICTION_WINDOW_SAMPLES = 250
# 我们将以检测到的“真正起点”为基准来构建窗口
# 所以不再需要 before/after 的概念

# --- 事件检测相关常量 ---
ENERGY_WINDOW_SAMPLES = 50
# 高阈值：用于确认事件的发生
EVENT_TRIGGER_THRESHOLD = 35.0
# 低阈值：用于回溯寻找事件的真正起点
EVENT_SEARCH_THRESHOLD = 15.0  # 应该远低于高阈值
# 最大回溯长度（点数），防止无限回溯
MAX_BACKTRACE_SAMPLES = 150


class ModelController(QObject):
    prediction_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # 缓冲区需要足够大，以容纳回溯所需的数据
        self.data_buffer = collections.deque(maxlen=PREDICTION_WINDOW_SAMPLES + MAX_BACKTRACE_SAMPLES)
        self.model = None
        self.device = None
        self.is_active = False
        #self.threshold = CONFIDENCE_THRESHOLD
        self.last_prediction_time = 0
        self.channel_indices = {'up': -1, 'down': -1, 'left': -1, 'right': -1}
        self.channel_names = []
        #self.is_collecting = False  # 新状态：是否正在为已触发的事件收集数据

    @pyqtSlot(list)
    def set_channel_names(self, names):
        """接收来自主窗口的通道名称列表，并查找EOG通道的索引。"""
        try:
            # 假设您的UI命名与此匹配
            self.channel_indices['up'] = names.index('Up')
            self.channel_indices['down'] = names.index('Down')
            self.channel_indices['left'] = names.index('Left')
            self.channel_indices['right'] = names.index('Right')
            print(f"ModelController: EOG channel indices updated: {self.channel_indices}")
        except ValueError as e:
            print(
                f"Warning: ModelController could not find required EOG channel name in list: {e}. Prediction will be disabled.")
            self.channel_indices = {key: -1 for key in self.channel_indices}

    @pyqtSlot(bool)
    def set_active(self, is_active):
        if is_active and self.model is None: self._load_model()
        if is_active:
            self.data_buffer.clear()
            self.last_prediction_time = 0
            self.is_collecting = False
        self.is_active = is_active
        print(f"Model Controller active status: {self.is_active}")

    @pyqtSlot(np.ndarray)
    def process_data_chunk(self, filtered_chunk):
        if not self.is_active or self.model is None or any(v == -1 for v in self.channel_indices.values()): return

        # 只将我们关心的4个EOG通道数据添加到缓冲区
        eog_chunk = filtered_chunk[[self.channel_indices['up'], self.channel_indices['down'],
                                    self.channel_indices['left'], self.channel_indices['right']], :]
        self.data_buffer.extend(eog_chunk.T)

        current_time = time.time()
        if (current_time - self.last_prediction_time) > COOLDOWN_PERIOD:
            self._detect_and_classify_event()

    def _detect_and_classify_event(self):
        """
        集成了双阈值检测、回溯和分类的完整流程。
        """
        # 1. 检查是否有足够数据进行高阈值检测
        if len(self.data_buffer) < ENERGY_WINDOW_SAMPLES:
            return

        # 2. 直接在原始的、未差值的4个通道上计算能量
        # 这样更稳健，不易受单个通道噪声影响
        current_segment = np.array(list(self.data_buffer)[-ENERGY_WINDOW_SAMPLES:]).T
        # 计算每个通道的标准差，然后取最大值作为能量
        energy = np.max(np.std(current_segment, axis=1))

        if energy > EVENT_TRIGGER_THRESHOLD:
            buffer_array = np.array(self.data_buffer)
            true_start_index = -1
            search_end = len(buffer_array)
            search_start = max(0, search_end - MAX_BACKTRACE_SAMPLES)

            for i in range(search_end - ENERGY_WINDOW_SAMPLES, search_start, -1):
                segment = buffer_array[i: i + ENERGY_WINDOW_SAMPLES].T
                local_energy = np.max(np.std(segment, axis=1))
                if local_energy < EVENT_SEARCH_THRESHOLD:
                    true_start_index = i + 1;
                    break

            if true_start_index == -1:
                true_start_index = max(0, len(buffer_array) - PREDICTION_WINDOW_SAMPLES)

            if len(buffer_array) >= true_start_index + PREDICTION_WINDOW_SAMPLES:
                window_data = buffer_array[true_start_index: true_start_index + PREDICTION_WINDOW_SAMPLES].T

                # 在这里进行差值计算
                v_eog = window_data[0, :] - window_data[1, :]  # Up - Down
                h_eog = window_data[3, :] - window_data[2, :]  # Right - Left
                input_signal = np.array([h_eog, v_eog])

                self._predict(input_signal)

                # 3. 不再清空整个缓冲区，而是移除已处理的事件部分
                # 这样可以保留事件之后的数据，有利于检测紧邻的下一个事件
                # 我们移除从起点到窗口结束的所有数据
                del self.data_buffer[:true_start_index + PREDICTION_WINDOW_SAMPLES]


    def _load_model(self):
        """加载模型，并自动选择 CPU/GPU"""
        if not os.path.exists(MODEL_PATH):
            print(f"Error: Model file not found at '{MODEL_PATH}'")
            return
        try:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            print(f"ModelController: Using device: {self.device}")

            self.model = RSCA_Net(in_channels=2, num_classes=len(CLASS_LABELS))
            self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
            self.model.to(self.device)
            self.model.eval()
            print("Info: RSCA_Net model loaded successfully by ModelController.")
        except Exception as e:
            print(f"Error loading model in ModelController: {e}")
            self.model = None

    def _predict(self, input_signal):
        data_tensor = torch.from_numpy(input_signal).unsqueeze(0).float().to(self.device)

        with torch.no_grad():
            outputs = self.model(data_tensor)

            # --- 关键修改：计算概率并应用阈值 ---
            # 1. 使用 softmax 将模型输出转换为概率
            probabilities = F.softmax(outputs, dim=1)

            # 2. 获取最高概率及其对应的类别索引
            max_prob, predicted_idx = torch.max(probabilities, 1)

            # 3. 将 tensor 转换为 python 数字
            confidence = max_prob.item()
            prediction_index = predicted_idx.item()

        # 4. 检查置信度是否达到阈值
        if confidence < self.threshold:
            # 如果置信度太低，则忽略这次预测
            # print(f"Prediction ignored (Confidence: {confidence:.2f} < {self.threshold})") # 取消注释以进行调试
            return

        # --- 如果置信度足够高，则继续执行后续逻辑 ---
        predicted_label = CLASS_LABELS[prediction_index]

        if predicted_label == 'fixation':
            # print(f"Prediction: FIXATION (Confidence: {confidence:.2f}, Ignored)") # 取消注释以进行调试
            return

        current_time = time.time()
        if(current_time - self.last_prediction_time < COOLDOWN_PERIOD):
            return

        final_prediction = predicted_label.upper()
        self.prediction_ready.emit(final_prediction)

        self.last_prediction_time = current_time

        print(f"Prediction: {final_prediction} (Confidence: {confidence:.2f})")