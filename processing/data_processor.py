import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import scipy.signal as signal
import time

try:
    from mne import create_info
    from mne.io import RawArray
    from mne import pick_types
except ImportError:
    print("Warning: MNE-Python is not installed. ICA cleaning will not be available.")
    create_info, RawArray = None, None

# --- 常量 ---
FFT_UPDATE_RATE = 4
FFT_WINDOW_SECONDS = 1
DOWNSAMPLE_FACTOR = 10
PROCESSING_INTERVAL_MS = 100
BANDS = {
    'Delta': [0.5, 4], 'Theta': [4, 8], 'Alpha': [8, 13],
    'Beta': [13, 30], 'Gamma': [30, 100]
}

class DataProcessor(QObject):
    recording_finished = pyqtSignal([dict], [type(None)])
    time_data_ready = pyqtSignal(np.ndarray)
    fft_data_ready = pyqtSignal(np.ndarray, np.ndarray)
    stats_ready = pyqtSignal(int, int)
    marker_added_live = pyqtSignal()
    band_power_ready = pyqtSignal(np.ndarray)

    filtered_data_ready = pyqtSignal(np.ndarray)

    calibration_data_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.raw_data_buffer = collections.deque()
        self.processing_timer = None
        self.sampling_rate = 1000  # 默认值
        self.num_channels = 8
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_data_buffer = collections.deque(maxlen=self.fft_samples)
        self.packet_counter = 0
        self.byte_counter = 0
        self.fft_timer = None
        self.is_recording = False
        self.recording_buffer = []
        self.markers = {'timestamps': [], 'labels': []}
        self.total_recorded_samples = 0
        self.filter_b, self.filter_a, self.filter_zi = None, None, None
        #self.update_filter_settings(0, 100.0)
        self.notch_enabled = False
        self.notch_b, self.notch_a, self.notch_zi = None, None, None
        self.current_hp = 0.0  # 保存当前滤波器设置以便重新计算
        self.current_lp = 100.0
        self.current_notch_freq = 50.0
        #self.update_notch_filter(False, 50.0)
        self.channel_names = []  # 将在 set_num_channels 中初始化
        self.set_num_channels(self.num_channels)  # 执行第一次初始化

        self.calibration_timer = None

        # --- 用于 ICA 校准的状态变量 ---
        self.is_calibrating_ica = False
        self.ica_calibration_buffer = []

        # --- 用于 ICA 应用的状态变量 ---
        self.ica_model = None
        self.ica_bad_indices = []
        self.ica_enabled = False

    @pyqtSlot(int)
    def set_num_channels(self, num_channels):
        """
        核心槽函数：设置新的通道数并重置所有依赖于它的状态。
        """
        print(f"DataProcessor: Setting number of channels to {num_channels}.")
        self.num_channels = num_channels
        self.channel_names = [f'CH {i + 1}' for i in range(self.num_channels)]

        # 滤波器状态的维度依赖于通道数，必须用新维度重置
        # 我们通过重新应用当前保存的滤波器设置来达到这个目的。
        self.update_filter_settings(self.current_hp, self.current_lp)
        self.update_notch_filter(self.notch_enabled, self.current_notch_freq)

    @pyqtSlot(list)
    def set_channel_names(self, names):
        """从主窗口接收更新后的通道名称列表"""
        if len(names) == self.num_channels:
            self.channel_names = names

    @pyqtSlot(int, str)
    def update_single_channel_name(self, channel_index, new_name):
        """实时更新单个通道的名称"""
        if 0 <= channel_index < len(self.channel_names):
            self.channel_names[channel_index] = new_name
            print(f"DataProcessor updated channel {channel_index} to '{new_name}'. Current names: {self.channel_names}")

    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sampling_rate == new_rate:
            return  # 如果采样率没有变化，则不做任何事

        print(f"Processor: Updating sample rate to {new_rate} Hz.")
        self.sampling_rate = new_rate
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)

        # 重新设置 FFT 缓冲区的最大长度
        self.fft_data_buffer = collections.deque(maxlen=self.fft_samples)

        # --- 关键：重新计算所有滤波器的系数 ---
        # 我们需要获取当前的滤波设置，然后用新的采样率重新应用它们
        # 这里我们假设滤波设置存储在某个地方，或者我们直接重新应用默认值
        # 一个更稳健的方法是让 ControlPanel 在发射 sample_rate_changed 后，
        # 立即再次发射 filter_settings_changed 和 notch_filter_changed。
        # 这里我们先手动重新配置。
        self.update_filter_settings(self.current_hp, self.current_lp)
        self.update_notch_filter(self.notch_enabled, self.current_notch_freq)

    @pyqtSlot(np.ndarray)
    def process_raw_data(self, data_chunk):
        if data_chunk.shape[0] != self.num_channels:
            print(
                f"Warning (Processor): Received data with {data_chunk.shape[0]} channels, but processor is configured for {self.num_channels}. Ignoring chunk.")
            return
        self.raw_data_buffer.append(data_chunk)

    def _process_buffered_data(self):
        if not self.raw_data_buffer: return
        all_chunks = []
        while self.raw_data_buffer:
            all_chunks.append(self.raw_data_buffer.popleft())
        if not all_chunks: return
        large_chunk = np.concatenate(all_chunks, axis=1)

        self.byte_counter += large_chunk.nbytes

        # --- 滤波链 ---
        if self.notch_enabled and self.notch_b is not None:
            notched_chunk, self.notch_zi = signal.lfilter(self.notch_b, self.notch_a, large_chunk, axis=1,
                                                          zi=self.notch_zi)
        else:
            notched_chunk = large_chunk
        if self.filter_b is not None and self.filter_a is not None:
            filtered_chunk, self.filter_zi = signal.lfilter(self.filter_b, self.filter_a, notched_chunk, axis=1,
                                                            zi=self.filter_zi)
        else:
            filtered_chunk = notched_chunk

        if self.is_calibrating_ica:
            self.ica_calibration_buffer.append(filtered_chunk)
            # # 检查是否已达到校准时长
            # if time.time() - self.calibration_start_time >= self.calibration_duration:
            #     self.finish_ica_calibration()

        if self.ica_enabled and self.ica_model is not None:
            # 我们将在后面的步骤中实现这个方法
            final_chunk = self.apply_ica_cleaning(filtered_chunk)
        else:
            final_chunk = filtered_chunk  # 如果未启用，则直接使用滤波后的数据

        self.filtered_data_ready.emit(final_chunk)

        # --- 关键修复 2：现在我们保存【滤波后】的数据 ---
        if self.is_recording:
            # 使用 filtered_chunk，而不是 large_chunk
            self.recording_buffer.append(final_chunk)
            # 样本数的累加保持不变
            self.total_recorded_samples += final_chunk.shape[1]

        # --- 后续处理 ---
        self.fft_data_buffer.extend(filtered_chunk.T)
        self.packet_counter += len(all_chunks)
        # downsampled_data = filtered_chunk[:, ::DOWNSAMPLE_FACTOR]
        # self.time_data_ready.emit(downsampled_data)
        self.time_data_ready.emit(final_chunk)

    @pyqtSlot(int)
    def start_ica_calibration(self, duration_seconds):
        if self.is_calibrating_ica:
            return  # 避免重复启动

        print(f"Starting ICA calibration for {duration_seconds} seconds.")
        # self.calibration_duration = duration_seconds
        self.ica_calibration_buffer = []
        self.is_calibrating_ica = True
        # self.calibration_start_time = time.time()
        self.calibration_timer.start(duration_seconds * 1000)

    def finish_ica_calibration(self):
        # 这个方法现在由定时器精确调用，其内部逻辑是正确的，无需修改
        if not self.is_calibrating_ica:
            # 防止因意外情况（如快速连续点击）导致重复调用
            return

        print("Finished collecting ICA calibration data via QTimer.")
        self.is_calibrating_ica = False

        if not self.ica_calibration_buffer:
            print("Warning: No data collected for ICA calibration.")
            # 即使没有数据，也需要通知UI训练失败或结束
            # 这里可以根据需要发出一个失败信号
            return

        full_calibration_data = np.concatenate(self.ica_calibration_buffer, axis=1)
        self.ica_calibration_buffer = []

        self.calibration_data_ready.emit(full_calibration_data)

    def apply_ica_cleaning(self, data_chunk):
        """
        使用预计算的矩阵高效地应用ICA伪迹去除。
        此版本会先分离出EEG和EOG通道，只对EEG通道进行清理，然后将结果合并。
        """
        # 检查矩阵和索引是否已准备好
        if self.unmixing_matrix_ is None or self.eeg_indices_ is None:
            return data_chunk

        try:
            # --- 1. 分离：从8通道数据中提取出EEG部分 ---
            # eeg_indices_ 是一个索引数组，例如 [2, 3, 4, 5, 6, 7]
            eeg_data = data_chunk[self.eeg_indices_, :]  # 形状变为 (6, n_samples)

            # --- 2. 处理：对6通道的EEG数据进行ICA清理 (这部分逻辑不变) ---
            ica_sources = self.unmixing_matrix_ @ eeg_data
            ica_sources *= self.zeroing_vector_[:, np.newaxis]
            cleaned_eeg_data = self.mixing_matrix_ @ ica_sources  # 形状仍为 (6, n_samples)

            # --- 3. 合并：创建一个新的8通道数据块，并将清理后的EEG和原始的EOG数据放回原位 ---
            # 创建一个和原始数据块形状一样、内容全为零的数组
            reconstructed_chunk = np.zeros_like(data_chunk)

            # 将清理过的EEG数据放回它们原来的位置
            reconstructed_chunk[self.eeg_indices_, :] = cleaned_eeg_data

            # 将原始的EOG数据原封不动地放回它们原来的位置
            if self.eog_indices_ is not None and len(self.eog_indices_) > 0:
                reconstructed_chunk[self.eog_indices_, :] = data_chunk[self.eog_indices_, :]

            return reconstructed_chunk

        except Exception as e:
            # 错误处理逻辑保持不变
            print(f"Error during matrix-based ICA cleaning: {e}. Disabling ICA.")
            self.ica_enabled = False
            self.unmixing_matrix_ = None
            return data_chunk

    @pyqtSlot(bool)
    def toggle_ica(self, enabled):
        if self.ica_model is None:
            print("Cannot enable ICA: model not trained.")
            self.ica_enabled = False
            return

        self.ica_enabled = enabled
        status = "enabled" if enabled else "disabled"
        print(f"Real-time ICA cleaning has been {status}.")

    @pyqtSlot(object, list)
    def set_ica_parameters(self, model, bad_indices):
        """
        接收训练好的ICA模型和坏道索引，并预先计算用于实时处理的矩阵和通道索引。
        """
        print(f"DataProcessor received ICA model. Bad components: {bad_indices}")
        self.ica_model = model
        self.ica_bad_indices = bad_indices

        if self.ica_model is not None:
            # --- 1. 获取EEG和EOG通道的索引 ---
            # MNE模型中保存了它训练时使用的通道信息
            # model.ch_names 是所有通道的列表，例如 ['EOG_V', 'EOG_H', 'CH 3', ...]
            # model.info['bads'] 在这里通常为空，但 model.info['projs'] 等信息可用
            # 一个更稳健的方法是直接从模型的信息中挑选出 'eeg' 和 'eog' 通道
            self.eeg_indices_ = pick_types(self.ica_model.info, eeg=True, eog=False, exclude=[])
            self.eog_indices_ = pick_types(self.ica_model.info, eeg=False, eog=True, exclude=[])
            print(f"Info: Identified EEG indices: {self.eeg_indices_}")
            print(f"Info: Identified EOG indices: {self.eog_indices_}")

            # --- 2. 预计算矩阵 (这部分不变) ---
            self.unmixing_matrix_ = self.ica_model.unmixing_matrix_
            self.mixing_matrix_ = self.ica_model.mixing_matrix_
            self.zeroing_vector_ = np.ones(self.ica_model.n_components_)
            self.zeroing_vector_[bad_indices] = 0
            print("Info: Pre-calculated ICA matrices for real-time cleaning.")
        else:
            self.unmixing_matrix_ = None
            self.mixing_matrix_ = None
            self.zeroing_vector_ = None
            self.eeg_indices_ = None
            self.eog_indices_ = None

    @pyqtSlot(bool, float)
    def update_notch_filter(self, enabled, freq):
        self.notch_enabled = enabled
        self.current_notch_freq = freq
        if not enabled:
            self.notch_b, self.notch_a, self.notch_zi = None, None, None
            print("Info: Notch filter disabled.")
            return
        Q = 30.0
        self.notch_b, self.notch_a = signal.iirnotch(freq, Q, fs=self.sampling_rate)
        zi = signal.lfilter_zi(self.notch_b, self.notch_a)
        self.notch_zi = np.tile(zi, (self.num_channels, 1))
        print(f"Info: Notch filter enabled at {freq} Hz.")

    def calculate_fft(self):
        if len(self.fft_data_buffer) < self.fft_samples: return
        data_window = np.array(self.fft_data_buffer).T
        windowed_data = data_window * np.hanning(self.fft_samples)
        magnitudes = np.abs(np.fft.rfft(windowed_data, axis=1)) / self.fft_samples
        frequencies = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)
        self.fft_data_ready.emit(frequencies, magnitudes)
        self.stats_ready.emit(self.packet_counter, self.byte_counter)
        self.packet_counter = 0
        self.byte_counter = 0
        psd = magnitudes ** 2
        band_powers = []
        for band_name, (low_freq, high_freq) in BANDS.items():
            freq_indices = np.where((frequencies >= low_freq) & (frequencies < high_freq))[0]
            if len(freq_indices) > 0:
                band_psd = psd[:, freq_indices]
                avg_psd_per_channel = np.mean(band_psd, axis=1)
                total_avg_power = np.mean(avg_psd_per_channel)
                band_powers.append(total_avg_power)
            else:
                band_powers.append(0)
        self.band_power_ready.emit(np.array(band_powers))

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
            print("No data recorded.")
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

    @pyqtSlot(float, float)
    def update_filter_settings(self, high_pass, low_pass):

        self.current_hp = high_pass
        self.current_lp = low_pass
        nyquist = 0.5 * self.sampling_rate
        # 允许高通为0，此时为低通滤波
        if high_pass < 0 or low_pass <= high_pass or low_pass >= nyquist:
            self.filter_b, self.filter_a, self.filter_zi = None, None, None
            print("Info: Filter disabled.")
            return
        if high_pass == 0:  # 低通滤波器
            self.filter_b, self.filter_a = signal.butter(N=4, Wn=low_pass, btype='lowpass', fs=self.sampling_rate)
            print(f"Info: Low-pass filter updated to {low_pass} Hz.")
        else:  # 带通滤波器
            self.filter_b, self.filter_a = signal.butter(N=4, Wn=[high_pass, low_pass], btype='bandpass',
                                                         fs=self.sampling_rate)
            print(f"Info: Band-pass filter updated to {high_pass}-{low_pass} Hz.")
        zi = signal.lfilter_zi(self.filter_b, self.filter_a)
        self.filter_zi = np.tile(zi, (self.num_channels, 1))

    # --- 修复 add_marker 中的变量名错误 ---
    @pyqtSlot(str)
    def add_marker(self, label):
        if self.is_recording:
            buffered_samples = sum(chunk.shape[1] for chunk in self.raw_data_buffer)
            marker_timestamp = self.total_recorded_samples + buffered_samples

            # 使用局部变量 marker_timestamp，而不是 self.marker_timestamp
            self.markers['timestamps'].append(marker_timestamp)
            self.markers['labels'].append(label)
            print(f"Marker '{label}' added at sample {marker_timestamp}")
            self.marker_added_live.emit()

    @pyqtSlot()
    def start(self):
        """
        这个方法在 DataProcessor 被移入新线程后才会被调用。
        这是创建属于该线程的 QTimer 对象的完美时机。
        """
        print(f"DataProcessor.start() is running on thread: {QThread.currentThreadId()}")

        # 1. 创建并配置所有定时器
        if self.processing_timer is None:
            self.processing_timer = QTimer(self)  # 将 self 作为父对象
            self.processing_timer.setInterval(PROCESSING_INTERVAL_MS)
            self.processing_timer.timeout.connect(self._process_buffered_data)

        if self.fft_timer is None:
            self.fft_timer = QTimer(self)  # 将 self 作为父对象
            self.fft_timer.setInterval(int(1000 / FFT_UPDATE_RATE))
            self.fft_timer.timeout.connect(self.calculate_fft)

        if self.calibration_timer is None:
            self.calibration_timer = QTimer(self)  # 将 self 作为父对象
            self.calibration_timer.setSingleShot(True)
            self.calibration_timer.timeout.connect(self.finish_ica_calibration)

        # 2. 清空缓冲区并启动常规定时器
        self.raw_data_buffer.clear()
        self.fft_data_buffer.clear()
        self.packet_counter = 0
        self.processing_timer.start()
        self.fft_timer.start()
        print("DataProcessor timers started successfully.")

    @pyqtSlot()
    def stop(self):
        # 停止所有定时器
        if self.processing_timer and self.processing_timer.isActive():
            self.processing_timer.stop()
        if self.fft_timer and self.fft_timer.isActive():
            self.fft_timer.stop()
        if self.calibration_timer and self.calibration_timer.isActive():
            self.calibration_timer.stop()
            if self.is_calibrating_ica:
                self.is_calibrating_ica = False
                self.ica_calibration_buffer = []
                print("ICA calibration was cancelled.")

        if self.is_recording:
            self.stop_recording()