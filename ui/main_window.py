# In ui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QSplitter
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup
import pyqtgraph as pg
from scipy.io import savemat, loadmat
import numpy as np

# 导入所有模块
from networking.data_receiver import DataReceiver
from processing.data_processor import DataProcessor
from ui.widgets.control_panel import ControlPanel
from ui.widgets.time_domain_widget import TimeDomainWidget
from ui.widgets.frequency_domain_widget import FrequencyDomainWidget
from .widgets.review_dialog import ReviewDialog
from networking.data_receiver import HOST, PORT
from .widgets.band_power_widget import BandPowerWidget

class FileSaver(QObject):
    finished = pyqtSignal(str) # Signal to report status back

    def save(self, filename, data_dict):
        try:
            savemat(filename, data_dict)
            self.finished.emit(f"File saved successfully to {filename}")
        except Exception as e:
            self.finished.emit(f"Error saving file: {e}")


class FileLoader(QObject):
    load_finished = pyqtSignal(dict)

    def load(self, filename):
        try:
            # squeeze_me=True 对于简化加载至关重要
            mat = loadmat(filename, squeeze_me=True)
            data = mat['data']
            sampling_rate = float(mat['sampling_rate'])

            clean_markers = None

            # --- 新的加载逻辑：优先检查新的扁平格式 ---
            if 'marker_timestamps' in mat and 'marker_labels' in mat:
                print("Info: Loading new flat marker format.")
                # 数据已经是干净的 1D 数组，直接使用
                flat_timestamps = np.atleast_1d(mat['marker_timestamps'])
                flat_labels = np.atleast_1d(mat['marker_labels'])

                clean_markers = {
                    'timestamps': flat_timestamps,
                    'labels': [str(item) for item in flat_labels]  # 确保标签是字符串
                }

            # --- 兼容旧格式的后备逻辑 ---
            elif 'markers' in mat:
                print("Warning: Loading legacy nested marker format.")
                markers_struct = mat['markers']

                # 在旧格式中，数据被包裹在一个结构里
                flat_timestamps = np.atleast_1d(markers_struct['timestamps'])
                flat_labels = np.atleast_1d(markers_struct['labels'])

                clean_markers = {
                    'timestamps': flat_timestamps,
                    'labels': [str(item) for item in flat_labels]
                }

            # (函数的其余部分)
            n_samples = data.shape[1]
            windowed_data = data * np.hanning(n_samples)
            magnitudes = np.abs(np.fft.rfft(windowed_data, axis=1)) / n_samples
            frequencies = np.fft.rfftfreq(n_samples, 1.0 / sampling_rate)

            result = {
                'data': data,
                'sampling_rate': sampling_rate,
                'freqs': frequencies,
                'mags': magnitudes,
                'markers': clean_markers,  # 使用我们处理好的干净数据
                'filename': filename.split('/')[-1]
            }
            self.load_finished.emit(result)

        except Exception as e:
            print(f"Error loading file: {e}")
            self.load_finished.emit({'error': str(e)})

class MainWindow(QMainWindow):
    sample_rate_changed = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ExGMP")
        self.setGeometry(50, 50, 1800, 1000)
        pg.setConfigOption('background', '#FFFFFF')
        pg.setConfigOption('foreground', '#333333')
        self.control_panel = ControlPanel()
        self.time_domain_widget = TimeDomainWidget()
        self.freq_domain_widget = FrequencyDomainWidget()
        self.band_power_widget = BandPowerWidget()
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        plot_layout = QVBoxLayout()
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self.freq_domain_widget)
        bottom_splitter.addWidget(self.band_power_widget)
        bottom_splitter.setSizes([700, 300])
        plot_layout.addWidget(self.time_domain_widget, 4)
        plot_layout.addWidget(bottom_splitter, 1)
        main_layout.addWidget(self.control_panel, 1)
        main_layout.addLayout(plot_layout, 4)

        self._create_menu_bar()

        self.review_dialog = None
        self.is_session_running = False
        self.setup_threads()
        self.setup_connections()

    def _create_menu_bar(self):
        # 获取 QMainWindow 默认的菜单栏
        menu_bar = self.menuBar()

        # 创建 "Settings" 菜单
        settings_menu = menu_bar.addMenu("Settings")

        # --- 创建采样率子菜单 ---
        sample_rate_menu = settings_menu.addMenu("Sample Rate")

        # 使用 QActionGroup 来确保单选效果
        self.rate_action_group = QActionGroup(self)
        self.rate_action_group.setExclusive(True)  # 设为互斥

        rates = [250, 500, 1000, 2000]
        for rate in rates:
            # 为每个采样率创建一个 QAction
            action = QAction(f"{rate} Hz", self)
            action.setCheckable(True)
            # 将采样率值作为自定义数据附加到 action 上
            action.setData(rate)

            # 设置默认选中的项
            if rate == 1000:
                action.setChecked(True)

            # 将 action 添加到菜单和 action group 中
            sample_rate_menu.addAction(action)
            self.rate_action_group.addAction(action)

        # 连接 action group 的触发信号到一个新的槽函数
        self.rate_action_group.triggered.connect(self._on_sample_rate_action)

    def _on_sample_rate_action(self, action):
        # 从被触发的 action 中获取我们之前附加的采样率数据
        rate = action.data()
        if rate:
            self.sample_rate_changed.emit(rate)
            print(f"Menu Event: Sample rate changed to {rate} Hz.")

    def setup_threads(self):
        self.receiver_thread = QThread()
        self.data_receiver = DataReceiver()
        self.data_receiver.moveToThread(self.receiver_thread)
        self.receiver_thread.started.connect(self.data_receiver.run)
        self.processor_thread = QThread()
        self.data_processor = DataProcessor()
        self.data_processor.moveToThread(self.processor_thread)
        self.processor_thread.started.connect(self.data_processor.start)

    def setup_connections(self):
        self.control_panel.open_file_clicked.connect(self.open_file)
        self.control_panel.start_recording_clicked.connect(self.data_processor.start_recording)
        self.control_panel.stop_recording_clicked.connect(self.data_processor.stop_recording)
        self.control_panel.add_marker_clicked.connect(self.data_processor.add_marker)
        self.data_processor.recording_finished.connect(self.save_recording_data)
        self.control_panel.connect_clicked.connect(self.start_session)
        self.control_panel.disconnect_clicked.connect(self.stop_session)
        self.control_panel.channel_visibility_changed.connect(self.time_domain_widget.toggle_visibility)
        self.control_panel.channel_scale_changed.connect(self.time_domain_widget.adjust_scale)
        self.data_receiver.connection_status.connect(self.control_panel.update_status)
        self.data_receiver.raw_data_received.connect(self.data_processor.process_raw_data)
        self.data_processor.time_data_ready.connect(self.time_domain_widget.update_plot)
        self.data_processor.fft_data_ready.connect(self.freq_domain_widget.update_fft)
        self.data_processor.stats_ready.connect(self.control_panel.update_stats)
        self.data_processor.marker_added_live.connect(self.time_domain_widget.show_live_marker)
        self.control_panel.plot_duration_changed.connect(self.time_domain_widget.set_plot_duration)
        self.control_panel.filter_settings_changed.connect(self.data_processor.update_filter_settings)
        self.data_processor.band_power_ready.connect(self.band_power_widget.update_plot)
        self.control_panel.notch_filter_changed.connect(self.data_processor.update_notch_filter)
        self.sample_rate_changed.connect(self.data_processor.set_sample_rate)
        self.sample_rate_changed.connect(self.time_domain_widget.set_sample_rate)

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open EEG Data File", "", "MATLAB files (*.mat)")
        if filename:
            self.control_panel.update_status(f"Loading {filename.split('/')[-1]}...")
            self.load_thread = QThread()
            self.file_loader = FileLoader()
            self.file_loader.moveToThread(self.load_thread)
            self.file_loader.load_finished.connect(self.on_file_loaded)
            self.load_thread.started.connect(lambda: self.file_loader.load(filename))
            self.load_thread.finished.connect(self.load_thread.deleteLater)
            self.load_thread.start()

    def on_file_loaded(self, result):
        if 'error' in result:
            self.control_panel.update_status(f"Error: {result['error']}")
        else:
            if not self.review_dialog:  # 如果对话框不存在则创建
                self.review_dialog = ReviewDialog(self)
            self.review_dialog.load_and_display(result)

        # 无论加载成功与否，都要根据 self.is_session_running 恢复状态栏
        if self.is_session_running:
            # 如果会话仍在运行，则将状态恢复为 "Connected"
            self.control_panel.update_status(f"Connected to {HOST}:{PORT}")
        else:
            # 否则，状态应为 "Disconnected"
            self.control_panel.update_status("Disconnected")

        self.load_thread.quit()

    def start_session(self):
        self.is_session_running = True
        self.time_domain_widget.clear_plots()
        self.freq_domain_widget.clear_plots()
        self.band_power_widget.clear_plots()
        self.receiver_thread.start()
        self.processor_thread.start()

    @pyqtSlot(object)  # 使用更通用的 'object' 类型来接收信号
    def save_recording_data(self, data_to_save):
        if data_to_save is None:
            # 如果接收到 None，更新状态并直接返回，不弹出文件对话框
            self.control_panel.update_status("Recording stopped (no data).")
            # 确保录制按钮状态被正确重置
            self.control_panel.reset_recording_buttons()
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Save EEG Data", "", "MATLAB files (*.mat)")
        if filename:
            self.save_thread = QThread()
            self.file_saver = FileSaver()
            self.file_saver.moveToThread(self.save_thread)
            self.file_saver.finished.connect(self.on_save_finished)
            self.save_thread.started.connect(lambda: self.file_saver.save(filename, data_to_save))
            self.save_thread.finished.connect(self.save_thread.deleteLater)
            self.save_thread.start()
        else:
            self.control_panel.update_status("Save cancelled.")
            self.control_panel.reset_recording_buttons()

    def on_save_finished(self, message):
        print(message)
        self.control_panel.reset_recording_buttons()
        self.control_panel.update_status(message)
        self.save_thread.quit()


    def stop_session(self):
        self.is_session_running = False
        self.data_receiver.stop()
        self.data_processor.stop()
        self.receiver_thread.quit()
        self.receiver_thread.wait()
        self.processor_thread.quit()
        self.processor_thread.wait()
        self.control_panel.update_status("Disconnected")

    def closeEvent(self, event):
        self.stop_session()
        event.accept()