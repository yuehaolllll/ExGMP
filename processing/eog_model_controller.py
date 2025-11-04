# In processing/model_controller.py

import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import torch
import torch.nn.functional as F
import os
import time

from .rsca_model import RSCA_Net

# --- 常量 ---
MODEL_PATH = "./models/rsca_net_8class_1.pth"
CLASS_LABELS = ['up', 'down', 'left', 'right', 'blink_once', 'blink_twice', 'blink_three', 'fixation']
CONFIDENCE_THRESHOLD = 0.75
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
MAX_BACKTRACE_SAMPLES = 100


class ModelController(QObject):
    prediction_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # 缓冲区需要足够大，以容纳回溯所需的数据
        self.data_buffer = collections.deque(maxlen=PREDICTION_WINDOW_SAMPLES + MAX_BACKTRACE_SAMPLES)
        self.model = None
        self.device = None
        self.is_active = False
        self.threshold = CONFIDENCE_THRESHOLD
        self.last_prediction_time = 0
        self.is_collecting = False  # 新状态：是否正在为已触发的事件收集数据

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
        if not self.is_active or self.model is None: return

        for sample in filtered_chunk.T:
            self.data_buffer.append(sample)

            # 只有在空闲状态（且不在冷却期）时，才去检测新事件
            current_time = time.time()
            if not self.is_collecting and (current_time - self.last_prediction_time) > COOLDOWN_PERIOD:
                self._detect_and_classify_event()

    def _detect_and_classify_event(self):
        """
        集成了双阈值检测、回溯和分类的完整流程。
        """
        # 1. 检查是否有足够数据进行高阈值检测
        if len(self.data_buffer) < ENERGY_WINDOW_SAMPLES:
            return

        # 2. 计算当前能量
        current_segment = np.array(list(self.data_buffer)[-ENERGY_WINDOW_SAMPLES:]).T
        h_eog = current_segment[1, :] - current_segment[0, :]
        v_eog = current_segment[2, :] - current_segment[3, :]
        energy = max(np.std(h_eog), np.std(v_eog))

        # 3. 检查是否触发高阈值
        if energy > EVENT_TRIGGER_THRESHOLD:
            # --- 事件被高阈值触发！---

            # 4. 执行回溯，寻找真正的起点
            buffer_array = np.array(self.data_buffer)  # 转换为numpy数组以便操作
            true_start_index = -1

            # 从触发点（末尾）向前搜索，最多回溯 MAX_BACKTRACE_SAMPLES 个点
            search_end_index = len(buffer_array)
            search_start_index = max(0, search_end_index - MAX_BACKTRACE_SAMPLES)

            for i in range(search_end_index - ENERGY_WINDOW_SAMPLES, search_start_index, -1):
                segment = buffer_array[i: i + ENERGY_WINDOW_SAMPLES].T
                h_eog_s = segment[1, :] - segment[0, :]
                v_eog_s = segment[2, :] - segment[3, :]
                local_energy = max(np.std(h_eog_s), np.std(v_eog_s))

                if local_energy < EVENT_SEARCH_THRESHOLD:
                    # 找到了！这是能量最后一次低于低阈值的点，我们认为它的下一个点是起点
                    true_start_index = i + 1
                    break

            # 如果没找到（例如动作一开始就非常剧烈），就使用一个近似的起点
            if true_start_index == -1:
                true_start_index = max(0, len(buffer_array) - PREDICTION_WINDOW_SAMPLES)

            # 5. 检查从找到的真正起点开始，是否有足够的数据构成一个完整窗口
            if len(buffer_array) >= true_start_index + PREDICTION_WINDOW_SAMPLES:
                # 6. 提取完整的、对齐的窗口
                window_data = buffer_array[true_start_index: true_start_index + PREDICTION_WINDOW_SAMPLES].T

                h_eog_w = window_data[1, :] - window_data[0, :]
                v_eog_w = window_data[2, :] - window_data[3, :]
                input_signal = np.array([h_eog_w, v_eog_w])

                # 7. 分类并重置
                self._predict(input_signal)
                self.last_prediction_time = time.time()  # 更新冷却计时器

                # 清空缓冲区，防止对同一事件的尾部进行重复检测
                self.data_buffer.clear()

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