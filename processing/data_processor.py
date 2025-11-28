# File: processing/data_processor.py

import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import scipy.signal as signal
import threading

# --- MNE 导入优化 ---
try:
    from mne import create_info, pick_types
    from mne.io import RawArray

    MNE_AVAILABLE = True
except ImportError:
    print("Warning: MNE-Python is not installed. ICA cleaning will not be available.")
    MNE_AVAILABLE = False
    create_info, pick_types, RawArray = None, None, None

# --- 常量定义 ---
FFT_UPDATE_RATE = 4  # 每秒更新 FFT 次数
FFT_WINDOW_SECONDS = 1.0  # FFT 时间窗口
PROCESSING_INTERVAL_MS = 100  # 数据处理间隔

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

        # 原始数据队列 (限制长度防止内存溢出)
        self.raw_data_buffer = collections.deque(maxlen=200)

        # 绘图 Buffer 使用 float32
        self.plot_buffer_samples = 12000
        self.plot_buffer = np.zeros((self.num_channels, self.plot_buffer_samples), dtype=np.float32)
        self.plot_buffer_ptr = 0
        self.plot_buffer_lock = threading.Lock()

        # FFT Buffer 使用 float32
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_buffer = np.zeros((self.num_channels, self.fft_samples), dtype=np.float32)
        self.fft_ptr = 0

        # 【优化】预计算窗函数和频率轴 (float32)
        self.fft_window = np.hanning(self.fft_samples).astype(np.float32)
        self.fft_freqs = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)

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
        self.filter_zi = None  # SOS 滤波器状态
        self.current_hp = 0.0
        self.current_lp = 100.0

        self.notch_enabled = False
        self.notch_b, self.notch_a = None, None
        self.notch_zi = None  # 陷波滤波器状态
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
        self.ica_filter_matrix_ = None
        self.eeg_indices_ = None
        self.eog_indices_ = None

        self.set_num_channels(self.num_channels)

    @pyqtSlot(int)
    def set_num_channels(self, num_channels):
        """重置通道数及相关 Buffer"""
        with self.plot_buffer_lock:
            if self.num_channels == num_channels and len(self.channel_names) == num_channels:
                return

            print(f"DataProcessor: Reconfiguring for {num_channels} channels...")
            self.num_channels = num_channels
            self.channel_names = [f'CH {i + 1}' for i in range(self.num_channels)]

            # 重置 Buffer (保持 float32)
            self.plot_buffer = np.zeros((num_channels, self.plot_buffer_samples), dtype=np.float32)
            self.plot_buffer_ptr = 0

            self.fft_buffer = np.zeros((num_channels, self.fft_samples), dtype=np.float32)
            self.fft_ptr = 0

            # 重新初始化滤波器状态
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

        # 更新 FFT 参数
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_window = np.hanning(self.fft_samples).astype(np.float32)
        self.fft_freqs = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)

        with self.plot_buffer_lock:
            self.fft_buffer = np.zeros((self.num_channels, self.fft_samples), dtype=np.float32)
            self.fft_ptr = 0

        self.update_filter_settings(self.current_hp, self.current_lp)
        self.update_notch_filter(self.notch_enabled, self.current_notch_freq)

    @pyqtSlot(float, float)
    def update_filter_settings(self, high_pass, low_pass):
        """设计 SOS 滤波器 (Float32)"""
        self.current_hp = high_pass
        self.current_lp = low_pass
        nyquist = 0.5 * self.sampling_rate

        if high_pass < 0 or low_pass <= high_pass or low_pass >= nyquist:
            self.filter_sos, self.filter_zi = None, None
            print("Info: Main filter disabled.")
            return

        try:
            if high_pass == 0:
                self.filter_sos = signal.butter(N=4, Wn=low_pass, btype='lowpass', fs=self.sampling_rate, output='sos')
            else:
                self.filter_sos = signal.butter(N=4, Wn=[high_pass, low_pass], btype='bandpass', fs=self.sampling_rate,
                                                output='sos')

            # 初始化滤波器状态 ZI
            # sosfilt_zi 返回 shape: (n_sections, 2)
            zi_per_channel = signal.sosfilt_zi(self.filter_sos)

            # 扩展为 (n_sections, n_channels, 2)
            zi_expanded = zi_per_channel[:, np.newaxis, :]
            # 转换为 float32
            self.filter_zi = np.tile(zi_expanded, (1, self.num_channels, 1)).astype(np.float32)

        except Exception as e:
            print(f"Error designing filter: {e}")
            self.filter_sos, self.filter_zi = None, None

    @pyqtSlot(bool, float)
    def update_notch_filter(self, enabled, freq):
        """设计陷波滤波器 (Float32)"""
        self.notch_enabled = enabled
        self.current_notch_freq = freq
        if not enabled:
            self.notch_b, self.notch_a, self.notch_zi = None, None, None
            return

        Q = 30.0
        b, a = signal.iirnotch(freq, Q, fs=self.sampling_rate)

        # 强制转换为 float32
        self.notch_b = b.astype(np.float32)
        self.notch_a = a.astype(np.float32)

        # 初始化状态 ZI
        zi = signal.lfilter_zi(self.notch_b, self.notch_a)
        # 扩展为 (n_channels, order-1)
        self.notch_zi = np.tile(zi, (self.num_channels, 1)).astype(np.float32)

    @pyqtSlot(np.ndarray)
    def process_raw_data(self, data_chunk):
        """接收原始数据 (假设已经是 float32)"""
        if data_chunk.shape[0] != self.num_channels:
            return
        self.raw_data_buffer.append(data_chunk)

    def _process_buffered_data(self):
        """
        核心处理循环：滤波 -> ICA -> Buffer更新
        全流程保持 float32 以获得最佳性能
        """
        if not self.raw_data_buffer: return

        # 1. 拼接所有待处理的数据块
        all_chunks = []
        while self.raw_data_buffer:
            all_chunks.append(self.raw_data_buffer.popleft())

        # 这里产生一次内存拷贝是必须的，但 float32 减小了开销
        large_chunk = np.concatenate(all_chunks, axis=1)

        self.byte_counter += large_chunk.nbytes
        self.packet_counter += len(all_chunks)

        # 2. 陷波滤波
        if self.notch_enabled and self.notch_b is not None:
            # lfilter 输出默认可能会变回 float64，取决于 scipy 版本，这里尽量保持类型
            notched_chunk, self.notch_zi = signal.lfilter(
                self.notch_b, self.notch_a, large_chunk, axis=1, zi=self.notch_zi
            )
            # 确保还是 float32
            if notched_chunk.dtype != np.float32:
                notched_chunk = notched_chunk.astype(np.float32)
        else:
            notched_chunk = large_chunk

        # 3. 主滤波器 (SOS)
        if self.filter_sos is not None:
            filtered_chunk, self.filter_zi = signal.sosfilt(
                self.filter_sos, notched_chunk, axis=1, zi=self.filter_zi
            )
            if filtered_chunk.dtype != np.float32:
                filtered_chunk = filtered_chunk.astype(np.float32)
        else:
            filtered_chunk = notched_chunk

        # 4. ICA 去伪迹
        if self.is_calibrating_ica:
            self.ica_calibration_buffer.append(filtered_chunk)

        if self.ica_enabled and self.ica_filter_matrix_ is not None:
            final_chunk = self.apply_ica_cleaning(filtered_chunk)
        else:
            final_chunk = filtered_chunk

        # 发出滤波后的数据信号
        self.filtered_data_ready.emit(final_chunk)

        # 5. 录制数据
        if self.is_recording:
            self.recording_buffer.append(final_chunk)
            self.total_recorded_samples += final_chunk.shape[1]

        # 6. 更新 FFT 环形缓冲区
        n_new = final_chunk.shape[1]
        if n_new > 0:
            start = self.fft_ptr
            end = start + n_new
            if end <= self.fft_samples:
                self.fft_buffer[:, start:end] = final_chunk
            else:
                # 环绕写入
                part1 = self.fft_samples - start
                part2 = n_new - part1
                self.fft_buffer[:, start:] = final_chunk[:, :part1]
                self.fft_buffer[:, :part2] = final_chunk[:, part1:]
            self.fft_ptr = end % self.fft_samples

        # 7. 更新 Plot 环形缓冲区 (含降采样)
        downsampled_data = final_chunk[:, ::self.downsample_factor]
        n_ds_samples = downsampled_data.shape[1]

        if n_ds_samples > 0:
            # 获取锁，写入绘图缓冲
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
        """计算 FFT 并发出信号"""
        # 1. 从 Ring Buffer 提取对齐的数据 (Copy)
        if self.fft_ptr == 0:
            data_ordered = self.fft_buffer.copy()
        else:
            data_ordered = np.concatenate((self.fft_buffer[:, self.fft_ptr:],
                                           self.fft_buffer[:, :self.fft_ptr]), axis=1)

        # 2. 去趋势 (In-place, 节省内存)
        # type='constant' 相当于减去均值
        signal.detrend(data_ordered, axis=1, type='constant', overwrite_data=True)

        # 3. 加窗 (In-place)
        data_ordered *= self.fft_window

        # 4. FFT 计算
        fft_complex = np.fft.rfft(data_ordered, axis=1)
        # 计算幅度并归一化
        magnitudes = np.abs(fft_complex) / self.fft_samples

        # 发送信号 (使用预计算的频率轴)
        self.fft_data_ready.emit(self.fft_freqs, magnitudes)

        # 顺便发送统计数据
        self.stats_ready.emit(self.packet_counter, self.byte_counter)
        self.packet_counter = 0
        self.byte_counter = 0

        # 5. 计算频带功率 (Band Power)
        psd = magnitudes ** 2
        band_powers = np.zeros(len(BANDS))

        for i, (band_name, (low, high)) in enumerate(BANDS.items()):
            # 生成布尔掩码
            mask = (self.fft_freqs >= low) & (self.fft_freqs < high)
            if np.any(mask):
                band_powers[i] = np.mean(psd[:, mask])

        self.band_power_ready.emit(band_powers)

    def get_plot_data(self):
        """
        非阻塞获取绘图数据。
        如果处理线程正在写 Buffer，这里不会死等，而是直接返回 None。
        这样 UI 线程永远不会被数据处理卡住。
        """
        if self.plot_buffer_lock.acquire(blocking=False):
            try:
                # 提取线性连续的数据
                data_part1 = self.plot_buffer[:, self.plot_buffer_ptr:]
                data_part2 = self.plot_buffer[:, :self.plot_buffer_ptr]
                return np.concatenate((data_part1, data_part2), axis=1)
            finally:
                self.plot_buffer_lock.release()

        # 如果锁被占用，返回 None，UI 这一帧跳过更新
        return None

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

    # --- ICA 相关功能 ---
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
        """预计算 ICA 空间滤波矩阵"""
        if not MNE_AVAILABLE: return

        print(f"DataProcessor received ICA model. Bad components: {bad_indices}")
        self.ica_model = model
        self.ica_bad_indices = bad_indices

        if self.ica_model is None:
            self.ica_filter_matrix_ = None
            return

        try:
            self.eeg_indices_ = pick_types(self.ica_model.info, eeg=True, eog=False, exclude=[])

            # 创建单位矩阵数据，模拟每个通道的脉冲
            n_eeg = len(self.eeg_indices_)
            identity_data = np.eye(n_eeg)

            dummy_info = create_info(model.ch_names, self.sampling_rate, ch_types='eeg')
            dummy_raw = RawArray(identity_data, dummy_info, verbose=False)

            # MNE Apply (这一步计算了混合->去除->反混合的全过程)
            model.apply(dummy_raw, exclude=bad_indices, verbose=False)

            # 提取出的就是我们要的线性变换矩阵
            # 【优化】转换为 float32
            self.ica_filter_matrix_ = dummy_raw.get_data().astype(np.float32)

            print(f"Info: ICA spatial filter matrix ready. Shape: {self.ica_filter_matrix_.shape}")
            self.ica_enabled = True

        except Exception as e:
            print(f"Error calculating ICA matrix: {e}")
            self.ica_enabled = False
            self.ica_filter_matrix_ = None

    def apply_ica_cleaning(self, data_chunk):
        """
        实时应用 ICA 清理
        data_chunk 和 matrix 都是 float32，运算极快
        """
        if self.ica_filter_matrix_ is None or self.eeg_indices_ is None:
            return data_chunk

        try:
            # 1. 提取 EEG
            eeg_data = data_chunk[self.eeg_indices_, :]

            # 2. 矩阵乘法 (去伪迹)
            cleaned_eeg_data = self.ica_filter_matrix_ @ eeg_data

            # 3. 填回数据 (Copy)
            reconstructed_chunk = data_chunk.copy()
            reconstructed_chunk[self.eeg_indices_, :] = cleaned_eeg_data

            return reconstructed_chunk

        except Exception as e:
            print(f"Error during real-time ICA cleaning: {e}. Disabling ICA.")
            self.ica_enabled = False
            return data_chunk