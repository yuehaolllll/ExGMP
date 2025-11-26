# import numpy as np
# import collections
# from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
# import scipy.signal as signal
# import time
# import threading
#
# # 尝试导入 MNE
# try:
#     from mne import create_info
#     from mne.io import RawArray
#     from mne import pick_types
# except ImportError:
#     print("Warning: MNE-Python is not installed. ICA cleaning will not be available.")
#     create_info, RawArray, pick_types = None, None, None
#
# # --- 常量定义 ---
# FFT_UPDATE_RATE = 4
# FFT_WINDOW_SECONDS = 1.0
# PROCESSING_INTERVAL_MS = 100
# BANDS = {
#     'Delta': [0.5, 4],
#     'Theta': [4, 8],
#     'Alpha': [8, 13],
#     'Beta': [13, 30],
#     'Gamma': [30, 100]
# }
#
#
# class DataProcessor(QObject):
#     # --- 信号定义 ---
#     recording_finished = pyqtSignal([dict], [type(None)])
#     fft_data_ready = pyqtSignal(np.ndarray, np.ndarray)
#     stats_ready = pyqtSignal(int, int)
#     marker_added_live = pyqtSignal()
#     band_power_ready = pyqtSignal(np.ndarray)
#     filtered_data_ready = pyqtSignal(np.ndarray)
#     calibration_data_ready = pyqtSignal(np.ndarray)
#
#     def __init__(self):
#         super().__init__()
#
#         # --- 基础配置 ---
#         self.sampling_rate = 1000
#         self.num_channels = 8
#         self.downsample_factor = 10
#
#         self.raw_data_buffer = collections.deque(maxlen=200)
#
#         self.plot_buffer_samples = 12000
#         self.plot_buffer = np.zeros((self.num_channels, self.plot_buffer_samples))
#         self.plot_buffer_ptr = 0
#         self.plot_buffer_lock = threading.Lock()
#
#         self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
#         self.fft_buffer = np.zeros((self.num_channels, self.fft_samples))
#         self.fft_ptr = 0
#
#         self.packet_counter = 0
#         self.byte_counter = 0
#         self.is_recording = False
#         self.recording_buffer = []
#         self.markers = {'timestamps': [], 'labels': []}
#         self.total_recorded_samples = 0
#         self.channel_names = []
#
#         # --- 滤波器状态 ---
#         self.filter_sos = None
#         self.filter_zi = None
#         self.current_hp = 0.0
#         self.current_lp = 100.0
#
#         self.notch_enabled = False
#         self.notch_b, self.notch_a = None, None
#         self.notch_zi = None
#         self.current_notch_freq = 50.0
#
#         self.processing_timer = None
#         self.fft_timer = None
#         self.calibration_timer = None
#
#         self.is_calibrating_ica = False
#         self.ica_calibration_buffer = []
#         self.ica_model = None
#         self.ica_bad_indices = []
#         self.ica_enabled = False
#         self.unmixing_matrix_ = None
#         self.mixing_matrix_ = None
#         self.eeg_indices_ = None
#         self.eog_indices_ = None
#
#         self.set_num_channels(self.num_channels)
#
#     @pyqtSlot(int)
#     def set_num_channels(self, num_channels):
#         with self.plot_buffer_lock:
#             if self.num_channels == num_channels and len(self.channel_names) == num_channels:
#                 return
#
#             print(f"DataProcessor: Reconfiguring for {num_channels} channels...")
#             self.num_channels = num_channels
#             self.channel_names = [f'CH {i + 1}' for i in range(self.num_channels)]
#
#             self.plot_buffer = np.zeros((num_channels, self.plot_buffer_samples))
#             self.plot_buffer_ptr = 0
#
#             self.fft_buffer = np.zeros((num_channels, self.fft_samples))
#             self.fft_ptr = 0
#
#             # 重新应用滤波器设置，此时会使用新的通道数计算 zi 维度
#             self.update_filter_settings(self.current_hp, self.current_lp)
#             self.update_notch_filter(self.notch_enabled, self.current_notch_freq)
#
#     @pyqtSlot(list)
#     def set_channel_names(self, names):
#         if len(names) == self.num_channels:
#             self.channel_names = names
#
#     @pyqtSlot(int, str)
#     def update_single_channel_name(self, channel_index, new_name):
#         if 0 <= channel_index < len(self.channel_names):
#             self.channel_names[channel_index] = new_name
#
#     @pyqtSlot(int)
#     def set_sample_rate(self, new_rate):
#         if self.sampling_rate == new_rate:
#             return
#
#         print(f"DataProcessor: Sample rate changed to {new_rate} Hz.")
#         self.sampling_rate = new_rate
#         self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
#
#         with self.plot_buffer_lock:
#             self.fft_buffer = np.zeros((self.num_channels, self.fft_samples))
#             self.fft_ptr = 0
#
#         self.update_filter_settings(self.current_hp, self.current_lp)
#         self.update_notch_filter(self.notch_enabled, self.current_notch_freq)
#
#     @pyqtSlot(float, float)
#     def update_filter_settings(self, high_pass, low_pass):
#         """
#         【修复版】使用 SOS 结构设计滤波器。
#         已修正 zi 的维度生成逻辑，适配 sosfilt 的要求。
#         """
#         self.current_hp = high_pass
#         self.current_lp = low_pass
#         nyquist = 0.5 * self.sampling_rate
#
#         if high_pass < 0 or low_pass <= high_pass or low_pass >= nyquist:
#             self.filter_sos, self.filter_zi = None, None
#             print("Info: Main filter disabled (invalid parameters).")
#             return
#
#         try:
#             if high_pass == 0:
#                 self.filter_sos = signal.butter(N=4, Wn=low_pass, btype='lowpass', fs=self.sampling_rate, output='sos')
#                 print(f"Info: Low-pass SOS filter set to {low_pass} Hz.")
#             else:
#                 self.filter_sos = signal.butter(N=4, Wn=[high_pass, low_pass], btype='bandpass', fs=self.sampling_rate,
#                                                 output='sos')
#                 print(f"Info: Band-pass SOS filter set to {high_pass}-{low_pass} Hz.")
#
#             # --- 维度修复关键点 ---
#             # sosfilt_zi 返回形状: (n_sections, 2)
#             zi_per_channel = signal.sosfilt_zi(self.filter_sos)
#
#             # sosfilt 要求 zi 形状为: (n_sections, batch_shape, 2)
#             # 我们的 batch_shape 是 n_channels (因为 axis=1 是时间，axis=0 是通道)
#             # 所以目标形状是: (n_sections, n_channels, 2)
#
#             # 1. 增加中间维度 -> (n_sections, 1, 2)
#             zi_expanded = zi_per_channel[:, np.newaxis, :]
#
#             # 2. 沿中间维度平铺 -> (n_sections, n_channels, 2)
#             self.filter_zi = np.tile(zi_expanded, (1, self.num_channels, 1))
#
#         except Exception as e:
#             print(f"Error designing filter: {e}")
#             self.filter_sos, self.filter_zi = None, None
#
#     @pyqtSlot(bool, float)
#     def update_notch_filter(self, enabled, freq):
#         """
#         陷波滤波器 (IIR)。
#         lfilter 的 zi 规则是 (n_channels, order-1)，与 sosfilt 不同，这里保持原逻辑。
#         """
#         self.notch_enabled = enabled
#         self.current_notch_freq = freq
#         if not enabled:
#             self.notch_b, self.notch_a, self.notch_zi = None, None, None
#             print("Info: Notch filter disabled.")
#             return
#
#         Q = 30.0
#         self.notch_b, self.notch_a = signal.iirnotch(freq, Q, fs=self.sampling_rate)
#
#         # lfilter_zi 形状: (order-1,)
#         zi = signal.lfilter_zi(self.notch_b, self.notch_a)
#
#         # lfilter 要求 zi 形状匹配 x 除了 filter axis 之外的维度
#         # x: (n_channels, samples), axis=1
#         # 目标 zi: (n_channels, order-1)
#         self.notch_zi = np.tile(zi, (self.num_channels, 1))
#         print(f"Info: Notch filter enabled at {freq} Hz.")
#
#     @pyqtSlot(np.ndarray)
#     def process_raw_data(self, data_chunk):
#         if data_chunk.shape[0] != self.num_channels:
#             return
#         self.raw_data_buffer.append(data_chunk)
#
#     def _process_buffered_data(self):
#         if not self.raw_data_buffer: return
#
#         all_chunks = []
#         while self.raw_data_buffer:
#             all_chunks.append(self.raw_data_buffer.popleft())
#
#         large_chunk = np.concatenate(all_chunks, axis=1)
#
#         self.byte_counter += large_chunk.nbytes
#         self.packet_counter += len(all_chunks)
#
#         # 1. 陷波滤波 (lfilter)
#         if self.notch_enabled and self.notch_b is not None:
#             notched_chunk, self.notch_zi = signal.lfilter(
#                 self.notch_b, self.notch_a, large_chunk, axis=1, zi=self.notch_zi
#             )
#         else:
#             notched_chunk = large_chunk
#
#         # 2. 主滤波器 (sosfilt)
#         if self.filter_sos is not None:
#             # 此时 self.filter_zi 应该是 (n_sections, n_channels, 2)，这是 sosfilt 期望的
#             filtered_chunk, self.filter_zi = signal.sosfilt(
#                 self.filter_sos, notched_chunk, axis=1, zi=self.filter_zi
#             )
#         else:
#             filtered_chunk = notched_chunk
#
#         # 3. ICA & 后续处理
#         if self.is_calibrating_ica:
#             self.ica_calibration_buffer.append(filtered_chunk)
#
#         if self.ica_enabled and self.ica_model is not None:
#             final_chunk = self.apply_ica_cleaning(filtered_chunk)
#         else:
#             final_chunk = filtered_chunk
#
#         self.filtered_data_ready.emit(final_chunk)
#
#         if self.is_recording:
#             self.recording_buffer.append(final_chunk)
#             self.total_recorded_samples += final_chunk.shape[1]
#
#         # 更新 FFT Buffer
#         n_new = final_chunk.shape[1]
#         if n_new > 0:
#             start = self.fft_ptr
#             end = start + n_new
#             if end <= self.fft_samples:
#                 self.fft_buffer[:, start:end] = final_chunk
#             else:
#                 part1 = self.fft_samples - start
#                 part2 = n_new - part1
#                 self.fft_buffer[:, start:] = final_chunk[:, :part1]
#                 self.fft_buffer[:, :part2] = final_chunk[:, part1:]
#             self.fft_ptr = end % self.fft_samples
#
#         # 更新 Plot Buffer
#         downsampled_data = final_chunk[:, ::self.downsample_factor]
#         n_ds_samples = downsampled_data.shape[1]
#
#         if n_ds_samples > 0:
#             with self.plot_buffer_lock:
#                 start = self.plot_buffer_ptr
#                 end = start + n_ds_samples
#                 if end <= self.plot_buffer_samples:
#                     self.plot_buffer[:, start:end] = downsampled_data
#                 else:
#                     part1 = self.plot_buffer_samples - start
#                     part2 = n_ds_samples - part1
#                     self.plot_buffer[:, start:] = downsampled_data[:, :part1]
#                     self.plot_buffer[:, :part2] = downsampled_data[:, part1:]
#                 self.plot_buffer_ptr = end % self.plot_buffer_samples
#
#     def calculate_fft(self):
#         data_ordered = np.concatenate((self.fft_buffer[:, self.fft_ptr:],
#                                        self.fft_buffer[:, :self.fft_ptr]), axis=1)
#
#         data_detrended = signal.detrend(data_ordered, axis=1, type='constant')
#         window = np.hanning(self.fft_samples)
#         windowed_data = data_detrended * window
#
#         fft_complex = np.fft.rfft(windowed_data, axis=1)
#         magnitudes = np.abs(fft_complex) / self.fft_samples
#         frequencies = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)
#
#         self.fft_data_ready.emit(frequencies, magnitudes)
#         self.stats_ready.emit(self.packet_counter, self.byte_counter)
#         self.packet_counter = 0
#         self.byte_counter = 0
#
#         psd = magnitudes ** 2
#         band_powers = []
#
#         for band_name, (low_freq, high_freq) in BANDS.items():
#             freq_indices = np.where((frequencies >= low_freq) & (frequencies < high_freq))[0]
#             if len(freq_indices) > 0:
#                 band_psd = psd[:, freq_indices]
#                 avg_power_per_channel = np.mean(band_psd, axis=1)
#                 total_avg_power = np.mean(avg_power_per_channel)
#                 band_powers.append(total_avg_power)
#             else:
#                 band_powers.append(0.0)
#
#         self.band_power_ready.emit(np.array(band_powers))
#
#     def get_plot_data(self):
#         with self.plot_buffer_lock:
#             data_part1 = self.plot_buffer[:, self.plot_buffer_ptr:]
#             data_part2 = self.plot_buffer[:, :self.plot_buffer_ptr]
#             return np.concatenate((data_part1, data_part2), axis=1)
#
#     @pyqtSlot()
#     def start(self):
#         print(f"DataProcessor.start() on thread: {QThread.currentThreadId()}")
#         if self.processing_timer is None:
#             self.processing_timer = QTimer(self)
#             self.processing_timer.setInterval(PROCESSING_INTERVAL_MS)
#             self.processing_timer.timeout.connect(self._process_buffered_data)
#
#         if self.fft_timer is None:
#             self.fft_timer = QTimer(self)
#             self.fft_timer.setInterval(int(1000 / FFT_UPDATE_RATE))
#             self.fft_timer.timeout.connect(self.calculate_fft)
#
#         if self.calibration_timer is None:
#             self.calibration_timer = QTimer(self)
#             self.calibration_timer.setSingleShot(True)
#             self.calibration_timer.timeout.connect(self.finish_ica_calibration)
#
#         self.raw_data_buffer.clear()
#         with self.plot_buffer_lock:
#             self.fft_buffer.fill(0)
#             self.fft_ptr = 0
#
#         self.packet_counter = 0
#         self.processing_timer.start()
#         self.fft_timer.start()
#
#     @pyqtSlot()
#     def stop(self):
#         if self.processing_timer: self.processing_timer.stop()
#         if self.fft_timer: self.fft_timer.stop()
#         if self.calibration_timer: self.calibration_timer.stop()
#         if self.is_recording: self.stop_recording()
#
#     @pyqtSlot(str)
#     def add_marker(self, label):
#         if self.is_recording:
#             buffered_samples = sum(chunk.shape[1] for chunk in self.raw_data_buffer)
#             marker_timestamp = self.total_recorded_samples + buffered_samples
#             self.markers['timestamps'].append(marker_timestamp)
#             self.markers['labels'].append(label)
#             print(f"Marker '{label}' added at sample {marker_timestamp}")
#             self.marker_added_live.emit()
#
#     @pyqtSlot()
#     def start_recording(self):
#         self.recording_buffer.clear()
#         self.markers = {'timestamps': [], 'labels': []}
#         self.total_recorded_samples = 0
#         self.is_recording = True
#
#     @pyqtSlot()
#     def stop_recording(self):
#         self.is_recording = False
#         self._process_buffered_data()
#         if not self.recording_buffer:
#             self.recording_finished.emit(None)
#             return
#
#         full_data = np.concatenate(self.recording_buffer, axis=1)
#         data_to_save = {
#             'data': full_data,
#             'sampling_rate': self.sampling_rate,
#             'channels': self.channel_names,
#             'marker_timestamps': np.array(self.markers['timestamps']),
#             'marker_labels': np.array(self.markers['labels']),
#         }
#         self.recording_finished.emit(data_to_save)
#
#     @pyqtSlot(bool)
#     def toggle_ica(self, enabled):
#         if self.ica_model is None:
#             print("Cannot enable ICA: model not trained.")
#             self.ica_enabled = False
#             return
#         self.ica_enabled = enabled
#         print(f"ICA cleaning {'enabled' if enabled else 'disabled'}.")
#
#     @pyqtSlot(int)
#     def start_ica_calibration(self, duration_seconds):
#         if self.is_calibrating_ica: return
#         print(f"Starting ICA calibration ({duration_seconds}s)...")
#         self.ica_calibration_buffer = []
#         self.is_calibrating_ica = True
#         self.calibration_timer.start(duration_seconds * 1000)
#
#     def finish_ica_calibration(self):
#         if not self.is_calibrating_ica: return
#         print("ICA calibration data collection finished.")
#         self.is_calibrating_ica = False
#         if not self.ica_calibration_buffer:
#             return
#         full_calib_data = np.concatenate(self.ica_calibration_buffer, axis=1)
#         self.ica_calibration_buffer = []
#         self.calibration_data_ready.emit(full_calib_data)
#
#     @pyqtSlot(object, list)
#     def set_ica_parameters(self, model, bad_indices):
#         """
#         接收训练好的 ICA 模型，并计算一个单一的线性投影矩阵用于实时去伪迹。
#         这种方法完美兼容 PCA 降维的情况。
#         """
#         print(f"DataProcessor received ICA model. Bad components to exclude: {bad_indices}")
#         self.ica_model = model
#         self.ica_bad_indices = bad_indices
#
#         if self.ica_model is None:
#             self.ica_filter_matrix_ = None
#             return
#
#         try:
#             # 1. 确定 EEG 和 EOG 通道索引
#             self.eeg_indices_ = pick_types(self.ica_model.info, eeg=True, eog=False, exclude=[])
#             self.eog_indices_ = pick_types(self.ica_model.info, eeg=False, eog=True, exclude=[])
#
#             # 2. 计算空间滤波器矩阵 (Spatial Filter Matrix)
#             # 我们创建一个单位矩阵 (Identity Matrix)，模拟每个通道的单位脉冲
#             # 矩阵大小为 (n_eeg_channels, n_eeg_channels)
#             n_eeg = len(self.eeg_indices_)
#             identity_data = np.eye(n_eeg)
#
#             # 创建一个临时的 RawArray，仅包含 EEG 通道
#             # 注意：必须使用 model.info 中的通道名，因为 model 是在这些通道上训练的
#             # model.ch_names 通常只包含用于 fit 的通道 (即 EEG 通道)
#             if len(model.ch_names) != n_eeg:
#                 print(f"Warning: Model channel count ({len(model.ch_names)}) != EEG indices count ({n_eeg}).")
#                 # 这是一个防御性检查，通常它们是相等的
#
#             # 创建 MNE 对象
#             import mne
#             dummy_info = mne.create_info(model.ch_names, self.sampling_rate, ch_types='eeg')
#             dummy_raw = mne.io.RawArray(identity_data, dummy_info, verbose=False)
#
#             # 3. 让 MNE 应用 ICA 清理逻辑 (apply)
#             # MNE 会自动处理 PCA、白化、反混合、剔除成分、混合、反白化等所有步骤
#             # 我们只需要告诉它剔除哪些坏成分
#             model.apply(dummy_raw, exclude=bad_indices, verbose=False)
#
#             # 4. 提取处理后的数据，这就是我们要的线性变换矩阵
#             self.ica_filter_matrix_ = dummy_raw.get_data()
#
#             print("Info: Successfully pre-calculated ICA spatial filter matrix.")
#             print(f"      Matrix shape: {self.ica_filter_matrix_.shape}")
#
#             self.ica_enabled = True  # 自动开启
#
#         except Exception as e:
#             print(f"Error calculating ICA matrix: {e}")
#             import traceback
#             traceback.print_exc()
#             self.ica_enabled = False
#             self.ica_filter_matrix_ = None
#
#     def apply_ica_cleaning(self, data_chunk):
#         """
#         使用预计算的矩阵进行一步式 ICA 清理。
#         """
#         # 检查矩阵是否准备好
#         if self.ica_filter_matrix_ is None or self.eeg_indices_ is None:
#             return data_chunk
#
#         try:
#             # 1. 提取 EEG 数据 (Shape: 6 x N)
#             eeg_data = data_chunk[self.eeg_indices_, :]
#
#             # 2. 应用空间滤波器 (Shape: 6x6 @ 6xN -> 6xN)
#             # 这一步完成了所有的 ICA 清理工作
#             cleaned_eeg_data = self.ica_filter_matrix_ @ eeg_data
#
#             # 3. 重构数据块
#             # 我们需要拷贝一份数据，否则可能修改原始引用
#             reconstructed_chunk = data_chunk.copy()
#
#             # 将清理后的 EEG 放回去
#             reconstructed_chunk[self.eeg_indices_, :] = cleaned_eeg_data
#
#             # EOG 通道保持原样 (data_chunk.copy() 已经保留了它们)
#
#             return reconstructed_chunk
#
#         except Exception as e:
#             print(f"Error during real-time ICA cleaning: {e}. Disabling ICA.")
#             self.ica_enabled = False
#             self.ica_filter_matrix_ = None
#             return data_chunk

# File: processing/data_processor.py

import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import scipy.signal as signal
import threading

# --- MNE 导入优化 ---
# 统一在模块加载时导入，避免运行时延迟
try:
    import mne
    from mne import create_info, pick_types
    from mne.io import RawArray

    MNE_AVAILABLE = True
except ImportError:
    print("Warning: MNE-Python is not installed. ICA cleaning will not be available.")
    MNE_AVAILABLE = False
    mne, create_info, pick_types, RawArray = None, None, None, None

# --- 常量定义 ---
FFT_UPDATE_RATE = 4
FFT_WINDOW_SECONDS = 1.0
PROCESSING_INTERVAL_MS = 100
BANDS = {
    'Delta': [0.5, 4],
    'Theta': [4, 8],
    'Alpha': [8, 13],
    'Beta': [13, 30],
    'Gamma': [30, 100]
}


class DataProcessor(QObject):
    # --- 信号定义 ---
    recording_finished = pyqtSignal([dict], [type(None)])
    fft_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    stats_ready = pyqtSignal(int, int)
    marker_added_live = pyqtSignal()
    band_power_ready = pyqtSignal(np.ndarray)
    filtered_data_ready = pyqtSignal(np.ndarray)
    calibration_data_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        # --- 基础配置 ---
        self.sampling_rate = 1000
        self.num_channels = 8
        self.downsample_factor = 10

        self.raw_data_buffer = collections.deque(maxlen=200)

        # 绘图缓冲
        self.plot_buffer_samples = 12000
        self.plot_buffer = np.zeros((self.num_channels, self.plot_buffer_samples))
        self.plot_buffer_ptr = 0
        self.plot_buffer_lock = threading.Lock()

        # FFT 缓冲与预计算
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_buffer = np.zeros((self.num_channels, self.fft_samples))
        self.fft_ptr = 0
        self.fft_window = np.hanning(self.fft_samples)  # 【优化】预计算窗函数
        self.fft_freqs = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)  # 【优化】预计算频率轴

        # 统计与录制
        self.packet_counter = 0
        self.byte_counter = 0
        self.is_recording = False
        self.recording_buffer = []
        self.markers = {'timestamps': [], 'labels': []}
        self.total_recorded_samples = 0
        self.channel_names = []

        # --- 滤波器状态 ---
        self.filter_sos = None
        self.filter_zi = None
        self.current_hp = 0.0
        self.current_lp = 100.0

        self.notch_enabled = False
        self.notch_b, self.notch_a = None, None
        self.notch_zi = None
        self.current_notch_freq = 50.0

        # 定时器
        self.processing_timer = None
        self.fft_timer = None
        self.calibration_timer = None

        # ICA 状态
        self.is_calibrating_ica = False
        self.ica_calibration_buffer = []
        self.ica_model = None
        self.ica_bad_indices = []
        self.ica_enabled = False
        self.ica_filter_matrix_ = None  # 重命名以保持一致
        self.eeg_indices_ = None
        self.eog_indices_ = None

        self.set_num_channels(self.num_channels)

    @pyqtSlot(int)
    def set_num_channels(self, num_channels):
        with self.plot_buffer_lock:
            if self.num_channels == num_channels and len(self.channel_names) == num_channels:
                return

            print(f"DataProcessor: Reconfiguring for {num_channels} channels...")
            self.num_channels = num_channels
            self.channel_names = [f'CH {i + 1}' for i in range(self.num_channels)]

            self.plot_buffer = np.zeros((num_channels, self.plot_buffer_samples))
            self.plot_buffer_ptr = 0

            self.fft_buffer = np.zeros((num_channels, self.fft_samples))
            self.fft_ptr = 0

            # 重新应用滤波器设置
            self.update_filter_settings(self.current_hp, self.current_lp)
            self.update_notch_filter(self.notch_enabled, self.current_notch_freq)

    @pyqtSlot(list)
    def set_channel_names(self, names):
        if len(names) == self.num_channels:
            self.channel_names = names

    @pyqtSlot(int, str)
    def update_single_channel_name(self, channel_index, new_name):
        if 0 <= channel_index < len(self.channel_names):
            self.channel_names[channel_index] = new_name

    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sampling_rate == new_rate:
            return

        print(f"DataProcessor: Sample rate changed to {new_rate} Hz.")
        self.sampling_rate = new_rate

        # 【优化】更新 FFT 相关参数和缓存
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_window = np.hanning(self.fft_samples)
        self.fft_freqs = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)

        with self.plot_buffer_lock:
            self.fft_buffer = np.zeros((self.num_channels, self.fft_samples))
            self.fft_ptr = 0

        self.update_filter_settings(self.current_hp, self.current_lp)
        self.update_notch_filter(self.notch_enabled, self.current_notch_freq)

    @pyqtSlot(float, float)
    def update_filter_settings(self, high_pass, low_pass):
        """
        使用 SOS 结构设计滤波器。
        保留了原有的 zi 维度修复逻辑。
        """
        self.current_hp = high_pass
        self.current_lp = low_pass
        nyquist = 0.5 * self.sampling_rate

        if high_pass < 0 or low_pass <= high_pass or low_pass >= nyquist:
            self.filter_sos, self.filter_zi = None, None
            print("Info: Main filter disabled (invalid parameters).")
            return

        try:
            if high_pass == 0:
                self.filter_sos = signal.butter(N=4, Wn=low_pass, btype='lowpass', fs=self.sampling_rate, output='sos')
                print(f"Info: Low-pass SOS filter set to {low_pass} Hz.")
            else:
                self.filter_sos = signal.butter(N=4, Wn=[high_pass, low_pass], btype='bandpass', fs=self.sampling_rate,
                                                output='sos')
                print(f"Info: Band-pass SOS filter set to {high_pass}-{low_pass} Hz.")

            # --- 维度修复逻辑 ---
            zi_per_channel = signal.sosfilt_zi(self.filter_sos)
            # 扩展维度: (n_sections, 2) -> (n_sections, 1, 2) -> (n_sections, n_channels, 2)
            zi_expanded = zi_per_channel[:, np.newaxis, :]
            self.filter_zi = np.tile(zi_expanded, (1, self.num_channels, 1))

        except Exception as e:
            print(f"Error designing filter: {e}")
            self.filter_sos, self.filter_zi = None, None

    @pyqtSlot(bool, float)
    def update_notch_filter(self, enabled, freq):
        """陷波滤波器 (IIR)"""
        self.notch_enabled = enabled
        self.current_notch_freq = freq
        if not enabled:
            self.notch_b, self.notch_a, self.notch_zi = None, None, None
            print("Info: Notch filter disabled.")
            return

        Q = 30.0
        self.notch_b, self.notch_a = signal.iirnotch(freq, Q, fs=self.sampling_rate)
        zi = signal.lfilter_zi(self.notch_b, self.notch_a)
        # 扩展维度: (order-1,) -> (n_channels, order-1)
        self.notch_zi = np.tile(zi, (self.num_channels, 1))
        print(f"Info: Notch filter enabled at {freq} Hz.")

    @pyqtSlot(np.ndarray)
    def process_raw_data(self, data_chunk):
        if data_chunk.shape[0] != self.num_channels:
            return
        self.raw_data_buffer.append(data_chunk)

    def _process_buffered_data(self):
        if not self.raw_data_buffer: return

        # 从 deque 中一次性取出所有数据
        all_chunks = []
        while self.raw_data_buffer:
            all_chunks.append(self.raw_data_buffer.popleft())

        large_chunk = np.concatenate(all_chunks, axis=1)

        self.byte_counter += large_chunk.nbytes
        self.packet_counter += len(all_chunks)

        # 1. 陷波滤波 (lfilter)
        if self.notch_enabled and self.notch_b is not None:
            notched_chunk, self.notch_zi = signal.lfilter(
                self.notch_b, self.notch_a, large_chunk, axis=1, zi=self.notch_zi
            )
        else:
            notched_chunk = large_chunk

        # 2. 主滤波器 (sosfilt)
        if self.filter_sos is not None:
            filtered_chunk, self.filter_zi = signal.sosfilt(
                self.filter_sos, notched_chunk, axis=1, zi=self.filter_zi
            )
        else:
            filtered_chunk = notched_chunk

        # 3. ICA & 后续处理
        if self.is_calibrating_ica:
            self.ica_calibration_buffer.append(filtered_chunk)

        if self.ica_enabled and self.ica_filter_matrix_ is not None:
            final_chunk = self.apply_ica_cleaning(filtered_chunk)
        else:
            final_chunk = filtered_chunk

        self.filtered_data_ready.emit(final_chunk)

        if self.is_recording:
            self.recording_buffer.append(final_chunk)
            self.total_recorded_samples += final_chunk.shape[1]

        # 更新 FFT Buffer (环形缓冲区)
        n_new = final_chunk.shape[1]
        if n_new > 0:
            start = self.fft_ptr
            end = start + n_new
            if end <= self.fft_samples:
                self.fft_buffer[:, start:end] = final_chunk
            else:
                part1 = self.fft_samples - start
                part2 = n_new - part1
                self.fft_buffer[:, start:] = final_chunk[:, :part1]
                self.fft_buffer[:, :part2] = final_chunk[:, part1:]
            self.fft_ptr = end % self.fft_samples

        # 更新 Plot Buffer
        downsampled_data = final_chunk[:, ::self.downsample_factor]
        n_ds_samples = downsampled_data.shape[1]

        if n_ds_samples > 0:
            with self.plot_buffer_lock:
                start = self.plot_buffer_ptr
                end = start + n_ds_samples
                if end <= self.plot_buffer_samples:
                    self.plot_buffer[:, start:end] = downsampled_data
                else:
                    part1 = self.plot_buffer_samples - start
                    part2 = n_ds_samples - part1
                    self.plot_buffer[:, start:] = downsampled_data[:, :part1]
                    self.plot_buffer[:, :part2] = downsampled_data[:, part1:]
                self.plot_buffer_ptr = end % self.plot_buffer_samples

    def calculate_fft(self):
        # 1. 构建有序数据 (Concatenate 是必要的，因为物理内存不连续)
        if self.fft_ptr == 0:
            data_ordered = self.fft_buffer.copy()
        else:
            data_ordered = np.concatenate((self.fft_buffer[:, self.fft_ptr:],
                                           self.fft_buffer[:, :self.fft_ptr]), axis=1)

        # 2. 【优化】去趋势 (原地修改)
        # overwrite_data=True 允许在 data_ordered 内存上直接操作
        data = signal.detrend(data_ordered, axis=1, type='constant', overwrite_data=True)

        # 3. 【优化】加窗 (原地修改)
        # 使用广播机制，避免创建新的 window 数组
        data *= self.fft_window

        # 4. FFT
        fft_complex = np.fft.rfft(data, axis=1)
        magnitudes = np.abs(fft_complex)

        # 5. 【优化】归一化 (原地修改)
        magnitudes /= self.fft_samples

        # 使用预计算的频率轴
        frequencies = self.fft_freqs

        self.fft_data_ready.emit(frequencies, magnitudes)
        self.stats_ready.emit(self.packet_counter, self.byte_counter)
        self.packet_counter = 0
        self.byte_counter = 0

        # 计算频带功率
        psd = magnitudes ** 2
        band_powers = []

        for band_name, (low_freq, high_freq) in BANDS.items():
            # 使用 numpy 的 searchsorted 可能比 where 更快，但这里数据量不大，where 也可以
            # 为了简单保持 boolean indexing，这部分性能瓶颈不明显
            freq_mask = (frequencies >= low_freq) & (frequencies < high_freq)
            if np.any(freq_mask):
                band_psd = psd[:, freq_mask]
                avg_power_per_channel = np.mean(band_psd, axis=1)
                total_avg_power = np.mean(avg_power_per_channel)
                band_powers.append(total_avg_power)
            else:
                band_powers.append(0.0)

        self.band_power_ready.emit(np.array(band_powers))

    def get_plot_data(self):
        with self.plot_buffer_lock:
            data_part1 = self.plot_buffer[:, self.plot_buffer_ptr:]
            data_part2 = self.plot_buffer[:, :self.plot_buffer_ptr]
            return np.concatenate((data_part1, data_part2), axis=1)

    @pyqtSlot()
    def start(self):
        print(f"DataProcessor.start() on thread: {QThread.currentThreadId()}")
        if self.processing_timer is None:
            self.processing_timer = QTimer(self)
            self.processing_timer.setInterval(PROCESSING_INTERVAL_MS)
            self.processing_timer.timeout.connect(self._process_buffered_data)

        if self.fft_timer is None:
            self.fft_timer = QTimer(self)
            self.fft_timer.setInterval(int(1000 / FFT_UPDATE_RATE))
            self.fft_timer.timeout.connect(self.calculate_fft)

        if self.calibration_timer is None:
            self.calibration_timer = QTimer(self)
            self.calibration_timer.setSingleShot(True)
            self.calibration_timer.timeout.connect(self.finish_ica_calibration)

        self.raw_data_buffer.clear()
        with self.plot_buffer_lock:
            self.fft_buffer.fill(0)
            self.fft_ptr = 0

        self.packet_counter = 0
        self.processing_timer.start()
        self.fft_timer.start()

    @pyqtSlot()
    def stop(self):
        if self.processing_timer: self.processing_timer.stop()
        if self.fft_timer: self.fft_timer.stop()
        if self.calibration_timer: self.calibration_timer.stop()
        if self.is_recording: self.stop_recording()

    @pyqtSlot(str)
    def add_marker(self, label):
        if self.is_recording:
            buffered_samples = sum(chunk.shape[1] for chunk in self.raw_data_buffer)
            marker_timestamp = self.total_recorded_samples + buffered_samples
            self.markers['timestamps'].append(marker_timestamp)
            self.markers['labels'].append(label)
            print(f"Marker '{label}' added at sample {marker_timestamp}")
            self.marker_added_live.emit()

    @pyqtSlot()
    def start_recording(self):
        self.recording_buffer.clear()
        self.markers = {'timestamps': [], 'labels': []}
        self.total_recorded_samples = 0
        self.is_recording = True

    @pyqtSlot()
    def stop_recording(self):
        self.is_recording = False
        self._process_buffered_data()
        if not self.recording_buffer:
            self.recording_finished.emit(None)
            return

        full_data = np.concatenate(self.recording_buffer, axis=1)
        data_to_save = {
            'data': full_data,
            'sampling_rate': self.sampling_rate,
            'channels': self.channel_names,
            'marker_timestamps': np.array(self.markers['timestamps']),
            'marker_labels': np.array(self.markers['labels']),
        }
        self.recording_finished.emit(data_to_save)

    @pyqtSlot(bool)
    def toggle_ica(self, enabled):
        if self.ica_model is None:
            print("Cannot enable ICA: model not trained.")
            self.ica_enabled = False
            return
        self.ica_enabled = enabled
        print(f"ICA cleaning {'enabled' if enabled else 'disabled'}.")

    @pyqtSlot(int)
    def start_ica_calibration(self, duration_seconds):
        if self.is_calibrating_ica: return
        print(f"Starting ICA calibration ({duration_seconds}s)...")
        self.ica_calibration_buffer = []
        self.is_calibrating_ica = True
        self.calibration_timer.start(duration_seconds * 1000)

    def finish_ica_calibration(self):
        if not self.is_calibrating_ica: return
        print("ICA calibration data collection finished.")
        self.is_calibrating_ica = False
        if not self.ica_calibration_buffer:
            return
        full_calib_data = np.concatenate(self.ica_calibration_buffer, axis=1)
        self.ica_calibration_buffer = []
        self.calibration_data_ready.emit(full_calib_data)

    @pyqtSlot(object, list)
    def set_ica_parameters(self, model, bad_indices):
        """
        接收训练好的 ICA 模型，并计算一个单一的线性投影矩阵用于实时去伪迹。
        """
        if not MNE_AVAILABLE:
            print("MNE not available, skipping ICA setup.")
            return

        print(f"DataProcessor received ICA model. Bad components to exclude: {bad_indices}")
        self.ica_model = model
        self.ica_bad_indices = bad_indices

        if self.ica_model is None:
            self.ica_filter_matrix_ = None
            return

        try:
            self.eeg_indices_ = pick_types(self.ica_model.info, eeg=True, eog=False, exclude=[])
            self.eog_indices_ = pick_types(self.ica_model.info, eeg=False, eog=True, exclude=[])

            n_eeg = len(self.eeg_indices_)
            identity_data = np.eye(n_eeg)

            if len(model.ch_names) != n_eeg:
                print(f"Warning: Model channel count ({len(model.ch_names)}) != EEG indices count ({n_eeg}).")

            # 使用全局导入的 mne
            dummy_info = create_info(model.ch_names, self.sampling_rate, ch_types='eeg')
            dummy_raw = RawArray(identity_data, dummy_info, verbose=False)

            model.apply(dummy_raw, exclude=bad_indices, verbose=False)

            self.ica_filter_matrix_ = dummy_raw.get_data()

            print("Info: Successfully pre-calculated ICA spatial filter matrix.")
            print(f"      Matrix shape: {self.ica_filter_matrix_.shape}")

            self.ica_enabled = True

        except Exception as e:
            print(f"Error calculating ICA matrix: {e}")
            import traceback
            traceback.print_exc()
            self.ica_enabled = False
            self.ica_filter_matrix_ = None

    def apply_ica_cleaning(self, data_chunk):
        """
        使用预计算的矩阵进行一步式 ICA 清理。
        """
        if self.ica_filter_matrix_ is None or self.eeg_indices_ is None:
            return data_chunk

        try:
            eeg_data = data_chunk[self.eeg_indices_, :]
            cleaned_eeg_data = self.ica_filter_matrix_ @ eeg_data

            reconstructed_chunk = data_chunk.copy()
            reconstructed_chunk[self.eeg_indices_, :] = cleaned_eeg_data

            return reconstructed_chunk

        except Exception as e:
            print(f"Error during real-time ICA cleaning: {e}. Disabling ICA.")
            self.ica_enabled = False
            self.ica_filter_matrix_ = None
            return data_chunk