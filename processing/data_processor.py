import numpy as np
import collections
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
import scipy.signal as signal

# --- 常量 ---
#SAMPLING_RATE = 2000
NUM_CHANNELS = 8
FFT_UPDATE_RATE = 4
FFT_WINDOW_SECONDS = 1
#FFT_SAMPLES = int(SAMPLING_RATE * FFT_WINDOW_SECONDS)
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
    stats_ready = pyqtSignal(int)
    marker_added_live = pyqtSignal()
    band_power_ready = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.raw_data_buffer = collections.deque()
        self.processing_timer = None
        self.sampling_rate = 1000  # 默认值
        self.fft_samples = int(self.sampling_rate * FFT_WINDOW_SECONDS)
        self.fft_data_buffer = collections.deque(maxlen=self.fft_samples)
        self.packet_counter = 0
        self.fft_timer = None
        self.is_recording = False
        self.recording_buffer = []
        self.markers = {'timestamps': [], 'labels': []}
        self.total_recorded_samples = 0
        self.filter_b, self.filter_a, self.filter_zi = None, None, None
        self.update_filter_settings(0, 100.0)
        self.notch_enabled = False
        self.notch_b, self.notch_a, self.notch_zi = None, None, None
        self.update_notch_filter(False, 50.0)
        self.channel_names = [f'CH {i + 1}' for i in range(NUM_CHANNELS)]

    @pyqtSlot(list)
    def set_channel_names(self, names):
        """从主窗口接收更新后的通道名称列表"""
        if len(names) == NUM_CHANNELS:
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
        # (注意：这部分逻辑的稳健性取决于您希望如何交互)
        self.update_filter_settings(0, 100.0)  # 重新应用默认值或当前UI值
        self.update_notch_filter(False, 50.0)

    @pyqtSlot(np.ndarray)
    def process_raw_data(self, data_chunk):
        self.raw_data_buffer.append(data_chunk)

    def _process_buffered_data(self):
        if not self.raw_data_buffer: return
        all_chunks = []
        while self.raw_data_buffer:
            all_chunks.append(self.raw_data_buffer.popleft())
        if not all_chunks: return
        large_chunk = np.concatenate(all_chunks, axis=1)

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

        # --- 关键修复 2：现在我们保存【滤波后】的数据 ---
        if self.is_recording:
            # 使用 filtered_chunk，而不是 large_chunk
            self.recording_buffer.append(filtered_chunk)
            # 样本数的累加保持不变
            self.total_recorded_samples += filtered_chunk.shape[1]

        # --- 后续处理 ---
        self.fft_data_buffer.extend(filtered_chunk.T)
        self.packet_counter += len(all_chunks)
        downsampled_data = filtered_chunk[:, ::DOWNSAMPLE_FACTOR]
        self.time_data_ready.emit(downsampled_data)

    # --- (update_notch_filter, calculate_fft, start/stop_recording 保持不变) ---
    @pyqtSlot(bool, float)
    def update_notch_filter(self, enabled, freq):
        self.notch_enabled = enabled
        if not enabled:
            self.notch_b, self.notch_a, self.notch_zi = None, None, None
            print("Info: Notch filter disabled.")
            return
        Q = 30.0
        self.notch_b, self.notch_a = signal.iirnotch(freq, Q, fs=self.sampling_rate)
        zi = signal.lfilter_zi(self.notch_b, self.notch_a)
        self.notch_zi = np.tile(zi, (NUM_CHANNELS, 1))
        print(f"Info: Notch filter enabled at {freq} Hz.")

    def calculate_fft(self):
        if len(self.fft_data_buffer) < self.fft_samples: return
        data_window = np.array(self.fft_data_buffer).T
        windowed_data = data_window * np.hanning(self.fft_samples)
        magnitudes = np.abs(np.fft.rfft(windowed_data, axis=1)) / self.fft_samples
        frequencies = np.fft.rfftfreq(self.fft_samples, 1.0 / self.sampling_rate)
        self.fft_data_ready.emit(frequencies, magnitudes)
        self.stats_ready.emit(self.packet_counter)
        self.packet_counter = 0
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

    # --- (update_filter_settings 保持不变) ---
    @pyqtSlot(float, float)
    def update_filter_settings(self, high_pass, low_pass):
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
        self.filter_zi = np.tile(zi, (NUM_CHANNELS, 1))

    # --- 关键修复 1：修复 add_marker 中的变量名错误 ---
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

    # --- (start 和 stop 方法保持不变) ---
    @pyqtSlot()
    def start(self):
        self.raw_data_buffer.clear()
        self.fft_data_buffer.clear()
        self.packet_counter = 0
        if self.processing_timer is None:
            self.processing_timer = QTimer()
            self.processing_timer.setInterval(PROCESSING_INTERVAL_MS)
            self.processing_timer.timeout.connect(self._process_buffered_data)
        self.processing_timer.start()
        if self.fft_timer is None:
            self.fft_timer = QTimer()
            self.fft_timer.setInterval(int(1000 / FFT_UPDATE_RATE))
            self.fft_timer.timeout.connect(self.calculate_fft)
        self.fft_timer.start()

    @pyqtSlot()
    def stop(self):
        if self.processing_timer: self.processing_timer.stop()
        if self.fft_timer: self.fft_timer.stop()
        if self.is_recording: self.stop_recording()