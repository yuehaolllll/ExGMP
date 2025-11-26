# File: ui/main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog,
                             QSplitter, QDialog, QWidgetAction, QMessageBox, QStackedWidget)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt, pyqtSlot, QTimer, QMetaObject, Q_ARG
from PyQt6.QtGui import QAction, QIcon, QPixmap, QGuiApplication
import pyqtgraph as pg
from scipy.io import savemat, loadmat
import numpy as np
import os
import sys

# 导入所有模块
from networking.data_receiver import DataReceiver
from processing.data_processor import DataProcessor
from ui.widgets.time_domain_widget import TimeDomainWidget
from ui.widgets.frequency_domain_widget import FrequencyDomainWidget
from .widgets.review_dialog import ReviewDialog
from .widgets.band_power_widget import BandPowerWidget
from networking.bluetooth_receiver import BluetoothDataReceiver
from .widgets.settings_panel import SettingsPanel
from .widgets.connection_panel import ConnectionPanel
from networking.serial_receiver import SerialDataReceiver
from ui.widgets.guidance_overlay import GuidanceOverlay
from .widgets.tools_panel import ToolsPanel
from processing.eog_model_controller import ModelController
from ui.widgets.eye_typing_widget import EyeTypingWidget
from processing.ica_processor import ICAProcessor
from .widgets.ica_component_dialog import ICAComponentDialog
from .widgets.header_bar import HeaderStatusWidget
from ui.widgets.recording_panel import RecordingPanel
from ui.widgets.display_filter_panel import DisplayFilterPanel
from ui.widgets.channel_settings_panel import ChannelSettingsPanel

# --- 优化点 1: 资源路径缓存 ---
_RESOURCE_CACHE = {}


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller. Cached. """
    if relative_path in _RESOURCE_CACHE:
        return _RESOURCE_CACHE[relative_path]

    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    path = os.path.join(base_path, relative_path)
    _RESOURCE_CACHE[relative_path] = path
    return path


class FileSaver(QObject):
    finished = pyqtSignal(str)

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
            mat = loadmat(filename, squeeze_me=True)
            data = mat['data']
            sampling_rate = float(mat['sampling_rate'])
            channel_names = mat.get('channels', [f'CH {i + 1}' for i in range(data.shape[0])])

            # 确保 channel_names 是列表
            if isinstance(channel_names, str):
                channel_names = [channel_names]
            else:
                channel_names = list(channel_names)

            clean_markers = None
            if 'marker_timestamps' in mat and 'marker_labels' in mat:
                print("Info: Loading new flat marker format.")
                flat_timestamps = np.atleast_1d(mat['marker_timestamps'])
                flat_labels = np.atleast_1d(mat['marker_labels'])
                clean_markers = {
                    'timestamps': flat_timestamps,
                    'labels': [str(item) for item in flat_labels]
                }
            elif 'markers' in mat:
                print("Warning: Loading legacy nested marker format.")
                markers_struct = mat['markers']
                flat_timestamps = np.atleast_1d(markers_struct['timestamps'])
                flat_labels = np.atleast_1d(markers_struct['labels'])
                clean_markers = {
                    'timestamps': flat_timestamps,
                    'labels': [str(item) for item in flat_labels]
                }

            n_samples = data.shape[1]
            # 计算 FFT 用于预览
            windowed_data = data * np.hanning(n_samples)
            magnitudes = np.abs(np.fft.rfft(windowed_data, axis=1)) / n_samples
            frequencies = np.fft.rfftfreq(n_samples, 1.0 / sampling_rate)

            result = {
                'data': data,
                'sampling_rate': sampling_rate,
                'freqs': frequencies,
                'mags': magnitudes,
                'markers': clean_markers,
                'filename': filename.split('/')[-1],
                'channels': channel_names
            }
            self.load_finished.emit(result)
        except Exception as e:
            print(f"Error loading file: {e}")
            self.load_finished.emit({'error': str(e)})


class MainWindow(QMainWindow):
    sample_rate_changed = pyqtSignal(int)
    frames_per_packet_changed = pyqtSignal(int)
    num_channels_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # 延迟导入非核心 UI 组件，加快启动速度
        from .widgets.refined_ble_scan_dialog import RefinedBleScanDialog
        from .widgets.splash_widget import SplashWidget
        from processing.acquisition_controller import AcquisitionController

        self.setMinimumSize(1100, 750)
        app_icon = QIcon(resource_path("icons/logo.png"))
        self.setWindowIcon(app_icon)
        self.setWindowTitle("ExGMP")

        # 全局配置 pyqtgraph
        pg.setConfigOption('background', '#FFFFFF')
        pg.setConfigOption('foreground', '#333333')

        # 1. 初始化后台线程
        self.setup_threads()
        self.acquisition_controller = AcquisitionController()

        # 2. 创建 UI
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.splash_widget = SplashWidget(resource_path("icons/splash_animation.gif"))
        self.stacked_widget.addWidget(self.splash_widget)

        main_plot_widget = self._setup_main_ui()
        self.stacked_widget.addWidget(main_plot_widget)

        self._create_menu_bar()

        # 3. 初始化对话框与状态
        self.ble_scan_dialog = RefinedBleScanDialog(self)
        self.review_dialog = None
        self.eye_typing_dialog = None
        self.is_session_running = False
        self.receiver_thread = None
        self.receiver_instance = None
        self.save_thread = None  # 初始化保存线程变量
        self.is_shutting_down = False
        self.current_connection_message = "Disconnected"

        # 4. 连接信号
        self.setup_connections()

        # 5. 启动持久线程
        self.ica_thread.start()
        self.eog_model_controller_thread.start()

        self.update_ui_on_connection(False)

    def _setup_main_ui(self):
        plot_container = QWidget()
        container_layout = QHBoxLayout(plot_container)
        container_layout.setContentsMargins(5, 5, 5, 5)

        self.time_domain_widget = TimeDomainWidget(self.data_processor)
        self.freq_domain_widget = FrequencyDomainWidget()
        self.band_power_widget = BandPowerWidget()

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.freq_domain_widget)
        right_splitter.addWidget(self.band_power_widget)
        right_splitter.setSizes([600, 400])

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.time_domain_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([900, 300])

        container_layout.addWidget(main_splitter)
        return plot_container

    def show_and_start_splash(self):
        available_geometry = QGuiApplication.primaryScreen().availableGeometry()
        w, h = available_geometry.width(), available_geometry.height()

        target_h = int(min(w, h) * 0.85)
        target_w = int(target_h * 1.33)
        self.resize(max(target_w, 1100), max(target_h, 750))

        center = available_geometry.center()
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

        self.show()
        self.splash_widget.start_animation()
        QTimer.singleShot(4000, self.switch_to_main_ui)

    def switch_to_main_ui(self):
        self.splash_widget.stop_animation()
        self.stacked_widget.setCurrentIndex(1)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.setCornerWidget(None, Qt.Corner.TopLeftCorner)

        # Connection
        conn_menu = menu_bar.addMenu("Connection")
        self.connection_panel = ConnectionPanel(self)
        self.connection_panel.connect_clicked.connect(self.on_connect_clicked)
        self.connection_panel.disconnect_clicked.connect(self.stop_session)
        conn_action = QWidgetAction(self)
        conn_action.setDefaultWidget(self.connection_panel)
        conn_menu.addAction(conn_action)

        # Settings
        settings_menu = menu_bar.addMenu("Settings")
        self.settings_panel = SettingsPanel(default_rate=1000, default_frames=50, default_channels=8)
        set_action = QWidgetAction(self)
        set_action.setDefaultWidget(self.settings_panel)
        settings_menu.addAction(set_action)

        self.settings_panel.sample_rate_changed.connect(self._on_sample_rate_changed)
        self.settings_panel.frames_per_packet_changed.connect(self._on_frames_changed)
        self.settings_panel.num_channels_changed.connect(self._on_num_channels_changed)
        self.settings_panel.gain_changed.connect(self.on_gain_setting_changed)

        # Filter
        filter_menu = menu_bar.addMenu("Filter")
        self.display_filter_panel = DisplayFilterPanel(self)
        filter_action = QWidgetAction(self)
        filter_action.setDefaultWidget(self.display_filter_panel)
        filter_menu.addAction(filter_action)

        # Channels
        ch_menu = menu_bar.addMenu("Channels")
        self.channel_settings_panel = ChannelSettingsPanel(parent=self)
        ch_action = QWidgetAction(self)
        ch_action.setDefaultWidget(self.channel_settings_panel)
        ch_menu.addAction(ch_action)

        # Recording
        rec_menu = menu_bar.addMenu("Recording")
        self.recording_panel = RecordingPanel(self)
        rec_action = QWidgetAction(self)
        rec_action.setDefaultWidget(self.recording_panel)
        rec_menu.addAction(rec_action)

        # Tools
        tools_menu = menu_bar.addMenu("Tools")
        self.tools_panel = ToolsPanel(self)
        tools_action = QWidgetAction(self)
        tools_action.setDefaultWidget(self.tools_panel)
        tools_menu.addAction(tools_action)

        # Application
        app_menu = menu_bar.addMenu("Application")
        self.eye_typing_action = QAction("⌨️  Eye Typing", self)
        self.eye_typing_action.setEnabled(False)
        self.eye_typing_action.triggered.connect(self._launch_eye_typer)
        app_menu.addAction(self.eye_typing_action)

        # Help
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About ExGMP", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

        # Status Bar
        self.header_bar = HeaderStatusWidget()
        menu_bar.setCornerWidget(self.header_bar, Qt.Corner.TopRightCorner)

    @pyqtSlot(int)
    def _on_sample_rate_changed(self, rate):
        self.sample_rate_changed.emit(rate)
        print(f"Menu Event: Sample rate changed to {rate} Hz.")

    @pyqtSlot(int)
    def _on_frames_changed(self, frames):
        self.frames_per_packet_changed.emit(frames)
        print(f"Menu Event: Frames per packet changed to {frames}.")

    def setup_threads(self):
        # Data Processor Thread
        self.processor_thread = QThread()
        self.data_processor = DataProcessor()
        self.data_processor.moveToThread(self.processor_thread)
        self.processor_thread.started.connect(self.data_processor.start)

        # ICA Thread
        self.ica_thread = QThread()
        self.ica_processor = ICAProcessor()
        self.ica_processor.moveToThread(self.ica_thread)

        # Model Controller Thread
        self.eog_model_controller_thread = QThread()
        self.eog_model_controller = ModelController()
        self.eog_model_controller.moveToThread(self.eog_model_controller_thread)

    def setup_connections(self):
        # Panels -> Actions
        self.recording_panel.open_file_clicked.connect(self.open_file)
        self.recording_panel.start_recording_clicked.connect(self._on_start_recording_clicked)
        self.recording_panel.stop_recording_clicked.connect(self.data_processor.stop_recording)
        self.recording_panel.add_marker_clicked.connect(self.data_processor.add_marker)

        self.display_filter_panel.plot_duration_changed.connect(self.time_domain_widget.set_plot_duration)
        self.display_filter_panel.filter_settings_changed.connect(self.data_processor.update_filter_settings)
        self.display_filter_panel.notch_filter_changed.connect(self.data_processor.update_notch_filter)

        self.channel_settings_panel.channel_visibility_changed.connect(self.time_domain_widget.toggle_visibility)
        self.channel_settings_panel.channel_name_changed.connect(self.time_domain_widget.update_channel_name)
        self.channel_settings_panel.channel_name_changed.connect(self.freq_domain_widget.update_channel_name)
        self.channel_settings_panel.channel_name_changed.connect(self.data_processor.update_single_channel_name)

        # DataProcessor -> UI
        self.data_processor.recording_finished.connect(self.save_recording_data)
        self.data_processor.fft_data_ready.connect(self.freq_domain_widget.update_realtime_fft)
        self.data_processor.stats_ready.connect(self.header_bar.update_stats)
        self.data_processor.marker_added_live.connect(self.time_domain_widget.show_live_marker)
        self.data_processor.band_power_ready.connect(self.band_power_widget.update_plot)
        self.data_processor.filtered_data_ready.connect(self.eog_model_controller.process_data_chunk)
        self.data_processor.calibration_data_ready.connect(self._on_calibration_data_ready)

        # Settings Signals -> Processor & Widgets
        self.sample_rate_changed.connect(self.data_processor.set_sample_rate)
        self.sample_rate_changed.connect(self.time_domain_widget.set_sample_rate)
        self.sample_rate_changed.connect(self.eog_model_controller.set_input_sample_rate)

        self.num_channels_changed.connect(self.channel_settings_panel.reconfigure_channels)
        self.num_channels_changed.connect(self.time_domain_widget.reconfigure_channels)
        self.num_channels_changed.connect(self.freq_domain_widget.reconfigure_channels)
        self.num_channels_changed.connect(self.data_processor.set_num_channels)

        # Tools -> Controllers
        self.tools_panel.eog_acquisition_triggered.connect(self.acquisition_controller.start)
        self.tools_panel.ica_toggle_changed.connect(self.data_processor.toggle_ica)
        self.tools_panel.ica_calibration_triggered.connect(self.data_processor.start_ica_calibration)

        # ICA & Model
        self.ica_processor.training_finished.connect(self._on_ica_training_finished)
        self.ica_processor.training_failed.connect(self._on_ica_training_failed)

        # Acquisition Controller
        self.acquisition_controller.started.connect(self._on_acquisition_started)
        self.acquisition_controller.finished.connect(self._on_acquisition_finished)
        self.acquisition_controller.start_recording_signal.connect(self.data_processor.start_recording)
        self.acquisition_controller.stop_recording_signal.connect(self.data_processor.stop_recording)
        self.acquisition_controller.add_marker_signal.connect(self.data_processor.add_marker)

    @pyqtSlot(int)
    def _on_num_channels_changed(self, num_channels):
        print(f"MainWindow: Detected channel count change to {num_channels}. Broadcasting...")
        self.num_channels_changed.emit(num_channels)

    @pyqtSlot(float)
    def on_gain_setting_changed(self, new_gain):
        print(f"Menu Event: Gain changed to x{new_gain}")
        if self.receiver_instance:
            self.receiver_instance.set_gain(new_gain)

    @pyqtSlot(str, dict)
    def on_connect_clicked(self, conn_type, params):
        if self.is_session_running: return

        if conn_type == "WiFi":
            self.start_session(conn_type)
        elif conn_type == "Bluetooth":
            # 避免多次连接槽
            try:
                self.ble_scan_dialog.device_selected.disconnect(self.on_ble_device_selected)
            except TypeError:
                pass
            self.ble_scan_dialog.device_selected.connect(self.on_ble_device_selected)
            self.ble_scan_dialog.exec_and_scan()
        elif conn_type == "Serial (UART)":
            self.start_session(conn_type, params=params)

    @pyqtSlot(str, str)
    def on_ble_device_selected(self, name, address):
        print(f"Device selected: {name} ({address})")
        self.start_session("Bluetooth", address=address)

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open EEG Data File", "", "MATLAB files (*.mat)")
        if filename:
            self.header_bar.update_status_message(f"Loading {filename.split('/')[-1]}...")
            self.load_thread = QThread()
            self.file_loader = FileLoader()
            self.file_loader.moveToThread(self.load_thread)
            self.file_loader.load_finished.connect(self.on_file_loaded)
            self.load_thread.started.connect(lambda: self.file_loader.load(filename))
            self.load_thread.finished.connect(self.load_thread.deleteLater)
            self.load_thread.start()

    def on_file_loaded(self, result):
        if 'error' in result:
            self.header_bar.update_status_message(f"Error: {result['error']}")
        else:
            if not self.review_dialog:
                self.review_dialog = ReviewDialog(self)
            self.review_dialog.load_and_display(result)

            if self.is_session_running:
                current_ch = self.settings_panel.get_current_channels()
                self.freq_domain_widget.reconfigure_channels(current_ch)

        self.header_bar.update_status_message(self.current_connection_message)
        self.load_thread.quit()

    def start_session(self, conn_type, address=None, params=None):
        if self.is_session_running: return

        # 1. 重置 UI 状态
        current_channels = self.settings_panel.get_current_channels()
        self.time_domain_widget.reconfigure_channels(current_channels)
        self.freq_domain_widget.reconfigure_channels(current_channels)
        self.band_power_widget.clear_plots()

        # 2. 计算参数
        frame_size = 3 + (current_channels * 3)
        V_REF = 4.5
        current_gain = self.settings_panel.get_current_gain()

        # 3. 实例化 Receiver
        if conn_type == "WiFi":
            self.receiver_instance = DataReceiver(
                num_channels=current_channels, v_ref=V_REF, gain=current_gain
            )
        elif conn_type == "Bluetooth":
            self.receiver_instance = BluetoothDataReceiver(
                device_address=address, num_channels=current_channels,
                frame_size=frame_size, v_ref=V_REF, gain=current_gain
            )
        elif conn_type == "Serial (UART)":
            if not params: return
            self.receiver_instance = SerialDataReceiver(
                port=params["port"], baudrate=params["baudrate"],
                num_channels=current_channels, frame_size=frame_size,
                v_ref=V_REF, gain=current_gain
            )
        else:
            return

        # 4. 连接信号
        if conn_type == "WiFi":
            self.receiver_instance.connection_status.connect(
                self.on_wifi_connected_send_commands,
                type=Qt.ConnectionType.SingleShotConnection
            )

        self.receiver_instance.connection_status.connect(self.on_connection_status_changed)
        self.receiver_instance.raw_data_received.connect(self.data_processor.process_raw_data)
        self.frames_per_packet_changed.connect(self.receiver_instance.set_frames_per_packet)

        # 5. 应用初始设置
        current_frames = self.settings_panel.get_current_frames()
        self.receiver_instance.set_frames_per_packet(current_frames)

        # 6. 启动线程
        self.receiver_thread = QThread()
        self.receiver_instance.moveToThread(self.receiver_thread)
        self.receiver_thread.started.connect(self.receiver_instance.run)
        self.receiver_thread.finished.connect(self.on_receiver_thread_finished)

        self.receiver_thread.start()
        # 确保 Processor 已经启动（通常在 init 已启动，但这里双保险）
        if not self.processor_thread.isRunning():
            self.processor_thread.start()

        self.time_domain_widget.start_updates()

    def stop_session(self, blocking=False):
        """停止所有会话活动"""
        self.time_domain_widget.stop_updates()
        if self.is_session_running:
            print("Stopping session...")

        self.is_session_running = False
        self.update_ui_on_connection(False)
        self.header_bar.update_status_message("Disconnecting...")

        # 断开信号 (使用 try-except 防止重复断开报错)
        if self.receiver_instance:
            try:
                self.receiver_instance.connection_status.disconnect(self.on_connection_status_changed)
                self.receiver_instance.raw_data_received.disconnect(self.data_processor.process_raw_data)
            except TypeError:
                pass

        # 停止 Processor 中的录制
        if self.data_processor and self.data_processor.is_recording:
            self.data_processor.stop_recording()

        # 停止 Receiver 线程
        if self.receiver_instance:
            self.receiver_instance.stop()

        if self.receiver_thread and self.receiver_thread.isRunning():
            self.receiver_thread.quit()
            if blocking:
                self.receiver_thread.wait(2000)

    def on_receiver_thread_finished(self):
        """线程结束回调"""
        if self.is_shutting_down: return
        print("Receiver thread finished.")
        self.receiver_instance = None
        self.receiver_thread = None

        self.current_connection_message = "Disconnected"
        self.update_ui_on_connection(False)
        self.header_bar.update_status_message("Disconnected")

    @pyqtSlot(str)
    def on_connection_status_changed(self, message):
        is_connected = "Connected" in message or "已连接" in message
        is_disconnected = "Disconnected" in message or "已断开" in message or "错误" in message

        self.header_bar.update_status_message(message)

        if is_connected:
            self.current_connection_message = message
            self.update_ui_on_connection(True)
        elif is_disconnected:
            self.current_connection_message = "Disconnected"
            if self.is_session_running:
                self.stop_session()
            else:
                self.update_ui_on_connection(False)

    def update_ui_on_connection(self, is_connected):
        self.is_session_running = is_connected
        self.connection_panel.update_status(is_connected)
        self.tools_panel.update_status(is_connected)
        self.eye_typing_action.setEnabled(is_connected)
        self.recording_panel.set_session_active(is_connected)

    @pyqtSlot(object)
    def save_recording_data(self, data_to_save):
        if data_to_save is None:
            self.header_bar.update_status_message("Recording stopped (no data).")
            self.recording_panel.set_recording_state(False)
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
            self.header_bar.update_status_message("Save cancelled.")
            self.recording_panel.set_session_active(True)
            self.recording_panel.set_recording_state(False)

    def on_save_finished(self, message):
        status_to_display = message
        if "File saved successfully to" in message:
            filename = os.path.basename(message.replace("File saved successfully to ", ""))
            print(f"Save successful: {filename}")
            status_to_display = f"Saved: {filename}"

        self.recording_panel.set_session_active(True)
        self.recording_panel.set_recording_state(False)
        self.header_bar.update_status_message(status_to_display)

        # 释放保存线程引用
        if self.save_thread:
            self.save_thread.quit()
            self.save_thread.wait()
            self.save_thread = None

    def _on_start_recording_clicked(self):
        current_names = self.channel_settings_panel.get_channel_names()
        self.data_processor.set_channel_names(current_names)
        self.data_processor.start_recording()

    def _on_acquisition_started(self):
        print("UI notified: Acquisition started.")
        self.guidance_overlay = GuidanceOverlay(parent=None)
        self.guidance_overlay.exit_clicked.connect(self.acquisition_controller.stop)
        self.acquisition_controller.update_state.connect(self.guidance_overlay.update_display)
        self.guidance_overlay.show_overlay()

        self.recording_panel.start_rec_btn.setEnabled(False)
        self.recording_panel.stop_rec_btn.setEnabled(False)

    def _on_acquisition_finished(self):
        print("UI notified: Acquisition finished.")
        if hasattr(self, 'guidance_overlay') and self.guidance_overlay:
            try:
                self.acquisition_controller.update_state.disconnect(self.guidance_overlay.update_display)
            except TypeError:
                pass
            self.guidance_overlay.hide_overlay()
            self.guidance_overlay.deleteLater()
            self.guidance_overlay = None

        self.update_ui_on_connection(self.is_session_running)

    # --- 优化点 2: 安全退出 ---
    def closeEvent(self, event):
        # 1. 检查是否有数据正在保存
        if self.save_thread and self.save_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Data is currently being saved. Please wait.")
            event.ignore()
            return

        self.is_shutting_down = True
        print("Close event triggered.")

        # 2. 停止会话
        self.stop_session(blocking=True)

        # 3. 停止 Processor 内部定时器
        if self.data_processor:
            self.data_processor.stop()

        # 4. 退出所有持久线程
        threads_to_wait = [
            self.processor_thread,
            self.ica_thread,
            self.eog_model_controller_thread
        ]

        for t in threads_to_wait:
            if t and t.isRunning():
                t.quit()
                t.wait(1000)  # 等待最多 1 秒

        print("All threads stopped. Closing.")
        event.accept()

    def show_about_dialog(self):
        about_dialog = QMessageBox(self)
        about_dialog.setWindowTitle("About ExGMP")
        logo_pixmap = QPixmap(resource_path("icons/logo.png"))
        scaled_logo = logo_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        about_dialog.setIconPixmap(scaled_logo)
        about_dialog.setTextFormat(Qt.TextFormat.RichText)
        about_dialog.setText(
            "<h2>ExG Monitor Platform</h2>"
            "<p>Version 1.0</p>"
            "<p>An application for ExG data acquisition and analysis.</p>"
            "<p>Developed by BioSignal Link.</p>"
            "<p>&copy; 2025.10.16</p>"
        )
        about_dialog.exec()

    def _launch_eye_typer(self):
        self.eye_typing_dialog = EyeTypingWidget(self)
        current_names = self.channel_settings_panel.get_channel_names()
        self.eog_model_controller.set_channel_names(current_names)

        self.eog_model_controller.prediction_ready.connect(self.eye_typing_dialog.on_prediction_received)
        self.eog_model_controller.set_active(True)

        self.eye_typing_dialog.exec()

        self.eog_model_controller.set_active(False)
        try:
            self.eog_model_controller.prediction_ready.disconnect(self.eye_typing_dialog.on_prediction_received)
        except TypeError:
            pass

        self.eye_typing_dialog.deleteLater()
        self.eye_typing_dialog = None

    @pyqtSlot(np.ndarray)
    def _on_calibration_data_ready(self, data):
        self.tools_panel.set_training_state()
        current_sample_rate = self.data_processor.sampling_rate
        QMetaObject.invokeMethod(self.ica_processor, "train",
                                 Qt.ConnectionType.QueuedConnection,
                                 Q_ARG(np.ndarray, data),
                                 Q_ARG(int, current_sample_rate))

    @pyqtSlot(object, np.ndarray, list)
    def _on_ica_training_finished(self, ica_model, components, suggested_indices):
        print("MainWindow: ICA training finished. Launching selector.")
        current_sample_rate = self.data_processor.sampling_rate

        dialog = ICAComponentDialog(
            components_data=components,
            sampling_rate=current_sample_rate,
            parent=self,
            suggested_indices=suggested_indices
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            bad_indices = dialog.get_selected_indices()
            self.data_processor.set_ica_parameters(ica_model, bad_indices)
            self.tools_panel.set_calibration_finished()
        else:
            self.tools_panel.update_status(self.is_session_running)

        dialog.deleteLater()

    @pyqtSlot(str)
    def _on_ica_training_failed(self, error_message):
        QMessageBox.critical(self, "ICA Training Error", error_message)
        self.tools_panel.update_status(self.is_session_running)

    @pyqtSlot(str)
    def on_wifi_connected_send_commands(self, message):
        print("Wi-Fi connected. Sending configuration commands...")

        # 采样率配置码表
        rate_map = {250: 0x96, 500: 0x95, 1000: 0x94, 2000: 0x93, 4000: 0x92, 8000: 0x91, 16000: 0x90}
        current_rate = self.settings_panel.get_current_sample_rate()
        current_channels = self.settings_panel.get_current_channels()

        sample_rate_code = rate_map.get(current_rate, 0x94)
        channel_mask = (1 << current_channels) - 1

        self.receiver_instance.update_active_channels(current_channels)

        import struct
        cmd_part = struct.pack('>BBBB', 0x5A, 0x01, sample_rate_code, channel_mask)
        checksum = sum(cmd_part) & 0xFF
        config_command = cmd_part + struct.pack('>B', checksum)

        cmd_part = struct.pack('>BB', 0x5A, 0x02)
        checksum = sum(cmd_part) & 0xFF
        start_command = cmd_part + struct.pack('>B', checksum)

        self.receiver_instance.send_command(config_command)
        QTimer.singleShot(100, lambda: self.receiver_instance.send_command(start_command))