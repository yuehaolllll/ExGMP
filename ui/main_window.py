# In ui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QSplitter, QDialog, QWidgetAction
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
from .widgets.ble_scan_dialog import BleScanDialog
from networking.bluetooth_receiver import BluetoothDataReceiver
from .widgets.settings_panel import SettingsPanel

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
    frames_per_packet_changed = pyqtSignal(int)
    connect_action_triggered = pyqtSignal(str)
    disconnect_action_triggered = pyqtSignal()
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

        self.ble_scan_dialog = BleScanDialog(self)

        self.review_dialog = None
        self.is_session_running = False
        self.receiver_thread = None
        self.receiver_instance = None
        self.setup_threads()
        self.setup_connections()

        self.is_shutting_down = False

    def _create_menu_bar(self):
        # 获取 QMainWindow 默认的菜单栏
        menu_bar = self.menuBar()
        # connection menu
        connection_menu = menu_bar.addMenu("Connection")
        # A. 创建连接方式子菜单
        conn_type_menu = connection_menu.addMenu("Connection Type")
        self.conn_type_group = QActionGroup(self)
        self.conn_type_group.setExclusive(True)
        conn_types = ["WiFi", "Bluetooth"]
        for conn_type in conn_types:
            action = QAction(conn_type, self)
            action.setCheckable(True)
            action.setData(conn_type)
            if conn_type == "WiFi":  # 默认选中 WiFi
                action.setChecked(True)
            conn_type_menu.addAction(action)
            self.conn_type_group.addAction(action)
        connection_menu.addSeparator()  # 添加一条分割线

        # B. 创建 Connect 和 Disconnect 动作
        self.connect_action = QAction("Connect", self)
        self.connect_action.triggered.connect(self._on_connect_action)
        connection_menu.addAction(self.connect_action)

        self.disconnect_action = QAction("Disconnect", self)
        self.disconnect_action.triggered.connect(self.disconnect_action_triggered.emit)
        self.disconnect_action.setEnabled(False)  # 初始为禁用
        connection_menu.addAction(self.disconnect_action)

        # 创建 "Settings" 菜单
        # --- 2. 新的、交互式的 Settings 菜单 ---
        settings_menu = menu_bar.addMenu("Settings")

        # 创建我们的自定义设置面板实例
        self.settings_panel = SettingsPanel(default_rate=1000, default_frames=50)

        # 创建一个 QWidgetAction
        widget_action = QWidgetAction(self)
        # 将我们的面板设置为这个 action 的默认 Widget
        widget_action.setDefaultWidget(self.settings_panel)

        # 将这个特殊的 action 添加到 Settings 菜单
        settings_menu.addAction(widget_action)

        # --- 3. 连接来自新面板的信号 ---
        # 注意：这里的信号是 self.settings_panel 发出的，而不是旧的 QActionGroup
        self.settings_panel.sample_rate_changed.connect(self._on_sample_rate_changed)
        self.settings_panel.frames_per_packet_changed.connect(self._on_frames_changed)

    def _on_connect_action(self):
        # 获取当前选中的连接类型
        selected_action = self.conn_type_group.checkedAction()
        if selected_action:
            conn_type = selected_action.data()
            self.connect_action_triggered.emit(conn_type)

    def update_menu_actions(self, is_connected):
        """根据连接状态更新 Connect/Disconnect 菜单项的可用性"""
        self.connect_action.setEnabled(not is_connected)
        self.disconnect_action.setEnabled(is_connected)

    @pyqtSlot(int)
    def _on_sample_rate_changed(self, rate):
        self.sample_rate_changed.emit(rate)
        print(f"Menu Event: Sample rate changed to {rate} Hz.")

    @pyqtSlot(int)
    def _on_frames_changed(self, frames):
        self.frames_per_packet_changed.emit(frames)
        print(f"Menu Event: Frames per packet changed to {frames}.")

    def setup_threads(self):
        # 只创建和配置数据处理器线程
        self.processor_thread = QThread()
        self.data_processor = DataProcessor()
        self.data_processor.moveToThread(self.processor_thread)
        self.processor_thread.started.connect(self.data_processor.start)

    def setup_connections(self):
        # Connection
        self.connect_action_triggered.connect(self.on_connect_clicked)
        self.disconnect_action_triggered.connect(self.stop_session)
        # Control Panel -> MainWindow / DataProcessor
        self.control_panel.open_file_clicked.connect(self.open_file)
        self.control_panel.start_recording_clicked.connect(self.data_processor.start_recording)
        self.control_panel.stop_recording_clicked.connect(self.data_processor.stop_recording)
        self.control_panel.add_marker_clicked.connect(self.data_processor.add_marker)
        # Control Panel -> TimeDomainWidget / DataProcessor (Filters, etc.)
        self.control_panel.channel_visibility_changed.connect(self.time_domain_widget.toggle_visibility)
        self.control_panel.channel_scale_changed.connect(self.time_domain_widget.adjust_scale)
        self.control_panel.notch_filter_changed.connect(self.data_processor.update_notch_filter)
        self.control_panel.plot_duration_changed.connect(self.time_domain_widget.set_plot_duration)
        self.control_panel.filter_settings_changed.connect(self.data_processor.update_filter_settings)
        # DataProcessor -> UI
        self.data_processor.recording_finished.connect(self.save_recording_data)
        self.data_processor.time_data_ready.connect(self.time_domain_widget.update_plot)
        self.data_processor.fft_data_ready.connect(self.freq_domain_widget.update_fft)
        self.data_processor.stats_ready.connect(self.control_panel.update_stats)
        self.data_processor.marker_added_live.connect(self.time_domain_widget.show_live_marker)
        self.data_processor.band_power_ready.connect(self.band_power_widget.update_plot)
        # Settings Menu -> DataProcessor / TimeDomainWidget
        self.sample_rate_changed.connect(self.data_processor.set_sample_rate)
        self.sample_rate_changed.connect(self.time_domain_widget.set_sample_rate)

    @pyqtSlot(str)
    def on_connect_clicked(self, conn_type):
        if self.is_session_running: return
        if conn_type == "WiFi":
            self.start_session(conn_type)
        elif conn_type == "Bluetooth":
            # 1. 临时连接信号
            self.ble_scan_dialog.device_selected.connect(self.on_ble_device_selected)
            # 2. 弹出对话框
            self.ble_scan_dialog.exec_and_scan()
            # 3. 操作结束后，断开连接，避免重复触发
            try:
                self.ble_scan_dialog.device_selected.disconnect(self.on_ble_device_selected)
            except TypeError:
                pass

    @pyqtSlot(str, str)
    def on_ble_device_selected(self, name, address):
        """
        这个槽函数在蓝牙扫描对话框中成功选择一个设备后被调用。
        """
        print(f"Device selected: {name} ({address})")
        # 使用获取到的设备地址，启动一个蓝牙会话
        self.start_session("Bluetooth", address=address)

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

    def start_session(self, conn_type, address=None):
        if self.is_session_running: return
        self.time_domain_widget.clear_plots();
        self.freq_domain_widget.clear_plots();
        self.band_power_widget.clear_plots()

        if conn_type == "WiFi":
            self.receiver_instance = DataReceiver()
        elif conn_type == "Bluetooth":
            self.receiver_instance = BluetoothDataReceiver(address)
        else:
            return

        # --- 在这里，在实例被创建后，立即连接它的信号 ---
        self.receiver_instance.connection_status.connect(self.on_connection_status_changed)
        self.receiver_instance.raw_data_received.connect(self.data_processor.process_raw_data)
        self.frames_per_packet_changed.connect(self.receiver_instance.set_frames_per_packet)

        current_frames = self.settings_panel.frames_button_group.checkedId()
        self.receiver_instance.set_frames_per_packet(current_frames)

        self.receiver_thread = QThread()
        self.receiver_instance.moveToThread(self.receiver_thread)
        self.receiver_thread.started.connect(self.receiver_instance.run)

        # --- 关键修复 1: 监听线程的结束信号 ---
        # 当线程真正结束后，我们再安全地清理对象
        self.receiver_thread.finished.connect(self.on_receiver_thread_finished)

        self.receiver_thread.start()
        self.processor_thread.start()

    def stop_session(self, blocking=False):
        """
        停止所有会话相关的活动。
        此方法经过重新设计，可以安全地多次调用。
        :param blocking: 如果为True，将阻塞并等待线程完全结束。
        """
        # 关键修复：移除了 'if not self.is_session_running: return'
        # 确保即使用户先点击断开再关闭窗口，清理逻辑也能在 closeEvent 中完整执行。

        # 仅在会话首次停止时打印消息，避免重复输出
        if self.is_session_running:
            print("Stopping session...")

        self.is_session_running = False  # 立即更新状态

        # 1. 立即更新UI并断开信号，防止任何排队的信号在UI销毁后被触发
        self.update_ui_on_connection(False)
        self.control_panel.update_status("Disconnecting...")

        if self.receiver_instance:
            try:
                self.receiver_instance.connection_status.disconnect(self.on_connection_status_changed)
                self.receiver_instance.raw_data_received.disconnect(self.data_processor.process_raw_data)
            except TypeError:
                pass  # 信号可能已经断开，忽略错误

        if self.data_processor:
            try:
                # 这个断开对于修复 update_stats 错误至关重要
                self.data_processor.stats_ready.disconnect(self.control_panel.update_stats)
            except TypeError:
                pass

        # 2. 停止数据处理器
        if self.processor_thread and self.processor_thread.isRunning():
            self.data_processor.stop()  # 停止内部的Timers
            self.processor_thread.quit()
            if blocking: self.processor_thread.wait()

        # 3. 停止数据接收器
        if self.receiver_instance:
            self.receiver_instance.stop()

        # 4. 请求接收器线程退出
        if self.receiver_thread and self.receiver_thread.isRunning():
            self.receiver_thread.quit()
            if blocking: self.receiver_thread.wait(2000)

        if not blocking:
            print("Non-blocking stop initiated.")

    def on_receiver_thread_finished(self):
        """
        这个槽函数只会在 receiver_thread 的事件循环完全退出后才被调用。
        这是进行最终清理和UI更新的最安全的地方。
        """
        if self.is_shutting_down:
            print("Receiver thread finished during shutdown, skipping final UI updates.")
            return
        print("Receiver thread has finished.")
        self.receiver_instance = None
        self.receiver_thread = None

        # 在所有后台活动都已确认停止后，最后一次、安全地更新UI
        self.update_ui_on_connection(False)
        self.control_panel.update_status("Disconnected")

    @pyqtSlot(str)
    def on_connection_status_changed(self, message):
        is_connected = "Connected" in message or "已连接" in message
        is_disconnected = "Disconnected" in message or "已断开" in message or "连接错误" in message
        self.control_panel.update_status(message)
        if is_connected:
            self.update_ui_on_connection(True)
        elif is_disconnected:
            if self.is_session_running:
                self.stop_session()
            else:
                self.update_ui_on_connection(False)

    def update_ui_on_connection(self, is_connected):
        self.is_session_running = is_connected
        self.update_menu_actions(is_connected)
        self.control_panel.start_rec_btn.setEnabled(is_connected)
        if not is_connected:
            self.control_panel.stop_rec_btn.setEnabled(False)
            self.control_panel.add_marker_btn.setEnabled(False)

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

    def closeEvent(self, event):
        """
        在关闭窗口时，以【阻塞】模式停止会话，确保所有后台活动
        在窗口被销毁前完全结束。
        """
        self.is_shutting_down = True
        print("Close event triggered.")
        # 1. 调用 stop_session 并传入 blocking=True
        self.stop_session(blocking=True)

        # 2. 在确认所有线程都已结束后，再安全地接受关闭事件
        print("All threads stopped. Accepting close event.")
        event.accept()