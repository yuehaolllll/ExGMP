# In ui/main_window.py
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog,
                             QSplitter, QDialog, QWidgetAction, QMessageBox, QStackedWidget)
from PyQt6.QtCore import QThread, QObject, pyqtSignal, Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QPixmap, QGuiApplication
import pyqtgraph as pg
from scipy.io import savemat, loadmat
import numpy as np
import os
import sys

# 导入所有模块
from networking.data_receiver import DataReceiver
from processing.data_processor import DataProcessor
from ui.widgets.control_panel import ControlPanel
from ui.widgets.time_domain_widget import TimeDomainWidget
from ui.widgets.frequency_domain_widget import FrequencyDomainWidget
from .widgets.review_dialog import ReviewDialog
from networking.data_receiver import HOST, PORT
from .widgets.band_power_widget import BandPowerWidget
from networking.bluetooth_receiver import BluetoothDataReceiver
from .widgets.settings_panel import SettingsPanel
from .widgets.connection_panel import ConnectionPanel
from networking.serial_receiver import SerialDataReceiver
from ui.widgets.guidance_overlay import GuidanceOverlay
from .widgets.tools_panel import ToolsPanel

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

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
            channel_names = mat.get('channels', [f'CH {i + 1}' for i in range(data.shape[0])])
            if isinstance(channel_names, str):
                channel_names = [channel_names]
            else:
                channel_names = list(channel_names)

            clean_markers = None

            # --- 优先检查新的扁平格式 ---
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
    def __init__(self):
        super().__init__()


        from .widgets.refined_ble_scan_dialog import RefinedBleScanDialog

        from .widgets.splash_widget import SplashWidget

        from processing.acquisition_controller import AcquisitionController

        self.setMinimumSize(1100, 750)
        # Logo
        app_icon = QIcon(resource_path("icons/logo.png"))
        self.setWindowIcon(app_icon)
        self.setWindowTitle("ExGMP")
        pg.setConfigOption('background', '#FFFFFF')
        pg.setConfigOption('foreground', '#333333')
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)  # 将堆叠窗口设为中心控件

        # --- 页面1: 启动动画 Widget ---
        self.splash_widget = SplashWidget(resource_path("icons/splash_animation.gif"))
        self.stacked_widget.addWidget(self.splash_widget)

        # --- 页面2: 主交互界面 Widget ---
        # 1. 创建一个容器 QWidget 用于主界面
        main_ui_widget = QWidget()
        # 2. 将您原来的所有UI组件放入这个容器中
        self._setup_main_ui(main_ui_widget)
        # 3. 将这个完整的容器添加到堆叠窗口
        self.stacked_widget.addWidget(main_ui_widget)

        self.ble_scan_dialog = RefinedBleScanDialog(self)

        self.review_dialog = None
        self.is_session_running = False
        self.receiver_thread = None
        self.receiver_instance = None
        self.setup_threads()

        # 创建采集控制器实例
        self.acquisition_controller = AcquisitionController()

        self.setup_connections()

        self.is_shutting_down = False

    def _setup_main_ui(self, parent_widget):
        """
        一个新方法，用于构建主交互界面。
        我们将原来 __init__ 中的UI构建代码移到了这里。
        """
        self.control_panel = ControlPanel()
        self.time_domain_widget = TimeDomainWidget()
        self.freq_domain_widget = FrequencyDomainWidget()
        self.band_power_widget = BandPowerWidget()

        main_layout = QHBoxLayout(parent_widget)  # 使用传入的父控件
        plot_layout = QVBoxLayout()
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self.freq_domain_widget)
        bottom_splitter.addWidget(self.band_power_widget)
        bottom_splitter.setSizes([700, 300])
        plot_layout.addWidget(self.time_domain_widget, 4)
        plot_layout.addWidget(bottom_splitter, 1)
        main_layout.addWidget(self.control_panel, 1)
        main_layout.addLayout(plot_layout, 4)

        # 菜单栏的创建现在也属于主UI的一部分
        self._create_menu_bar()

    def show_and_start_splash(self):
        """
        一个由 main.py 调用的新方法，用于显示窗口并开始启动流程。
        """

        # 1. 获取可用的屏幕尺寸
        available_geometry = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = available_geometry.width()
        screen_height = available_geometry.height()

        # 2. 找到屏幕宽度和高度中较小的一边
        shorter_side = min(screen_width, screen_height)

        # 3. 基于较小的一边，计算一个合适的“类正方形”尺寸
        # 我们可以让宽度稍微大一些，例如 宽高比为 4:3 或 5:4
        scale_factor = 0.9  # 使用屏幕较小边的 90%，您可以调整这个比例
        window_height = int(shorter_side * scale_factor)
        window_width = int(window_height * (4 / 3))  # 设置宽高比为 4:3

        # 4. 确保计算出的尺寸不小于我们设定的最小尺寸
        min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
        final_width = max(window_width, min_w)
        final_height = max(window_height, min_h)

        self.resize(final_width, final_height)

        # 3. 将窗口移动到屏幕中央
        # 这个方法比之前的 frameGeometry() 更简洁可靠
        window_center_point = available_geometry.center()
        self.move(int(window_center_point.x() - self.width() / 2),
                  int(window_center_point.y() - self.height() / 2))

        # 2. 显示窗口
        self.show()

        # 3. 开始播放动画
        self.splash_widget.start_animation()

        # 4. 设置定时器，在4秒后切换到主界面
        QTimer.singleShot(4000, self.switch_to_main_ui)

    def switch_to_main_ui(self):
        """切换到主交互界面"""
        self.splash_widget.stop_animation()
        self.stacked_widget.setCurrentIndex(1)  # 切换到索引为1的Widget

    def _create_menu_bar(self):
        # 获取 QMainWindow 默认的菜单栏
        menu_bar = self.menuBar()
        # connection menu
        connection_menu = menu_bar.addMenu("Connection")

        # 创建我们的自定义连接面板实例
        self.connection_panel = ConnectionPanel(self)

        # 将面板的信号直接连接到 MainWindow 的槽函数
        self.connection_panel.connect_clicked.connect(self.on_connect_clicked)
        self.connection_panel.disconnect_clicked.connect(self.stop_session)

        # 创建一个 QWidgetAction 来容纳我们的面板
        conn_widget_action = QWidgetAction(self)
        conn_widget_action.setDefaultWidget(self.connection_panel)

        # 将这个特殊的 action 添加到菜单
        connection_menu.addAction(conn_widget_action)

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

        tools_menu = menu_bar.addMenu("Tools")
        self.tools_panel = ToolsPanel(self)
        tools_widget_action = QWidgetAction(self)
        tools_widget_action.setDefaultWidget(self.tools_panel)
        tools_menu.addAction(tools_widget_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About ExGMP", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

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
        # Control Panel -> MainWindow / DataProcessor
        self.control_panel.open_file_clicked.connect(self.open_file)
        #self.control_panel.start_recording_clicked.connect(self.data_processor.start_recording)
        self.control_panel.start_recording_clicked.connect(self._on_start_recording_clicked)
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
        # Edit channel names
        self.control_panel.channel_name_changed.connect(self.time_domain_widget.update_channel_name)
        self.control_panel.channel_name_changed.connect(self.freq_domain_widget.update_channel_name)
        self.control_panel.channel_name_changed.connect(self.data_processor.update_single_channel_name)

        self.tools_panel.eog_acquisition_triggered.connect(self.acquisition_controller.start)

        self.acquisition_controller.started.connect(self._on_acquisition_started)
        self.acquisition_controller.finished.connect(self._on_acquisition_finished)
        self.acquisition_controller.start_recording_signal.connect(self.data_processor.start_recording)
        self.acquisition_controller.stop_recording_signal.connect(self.data_processor.stop_recording)
        self.acquisition_controller.add_marker_signal.connect(self.data_processor.add_marker)

    @pyqtSlot(str, dict)  # 明确指定接收的参数类型
    def on_connect_clicked(self, conn_type, params):
        if self.is_session_running: return

        if conn_type == "WiFi":
            self.start_session(conn_type)
        elif conn_type == "Bluetooth":
            self.ble_scan_dialog.device_selected.connect(self.on_ble_device_selected)
            self.ble_scan_dialog.exec_and_scan()
            try:
                self.ble_scan_dialog.device_selected.disconnect(self.on_ble_device_selected)
            except TypeError:
                pass
        elif conn_type == "Serial (UART)":
            self.start_session(conn_type, params=params)

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

    def start_session(self, conn_type, address=None, params=None):
        if self.is_session_running: return
        self.time_domain_widget.clear_plots();
        self.freq_domain_widget.clear_plots();
        self.band_power_widget.clear_plots()

        if conn_type == "WiFi":
            self.receiver_instance = DataReceiver()
        elif conn_type == "Bluetooth":
            self.receiver_instance = BluetoothDataReceiver(address)
        elif conn_type == "Serial (UART)":
            if not params:
                print("Error: Serial connection requires parameters.")
                return
            self.receiver_instance = SerialDataReceiver(port=params["port"], baudrate=params["baudrate"])
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
        self.connection_panel.update_status(is_connected)
        self.tools_panel.update_status(is_connected)
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
        status_to_display = message

        if "File saved successfully to" in message:
            # 1. 提取文件名用于打印日志（方便调试）
            filepath = message.replace("File saved successfully to ", "")
            filename = os.path.basename(filepath)
            print(f"Save successful: {filename}")

            # 2. 创建一个简短的消息用于UI显示
            status_to_display = f"Saved: {filename}"

        self.control_panel.reset_recording_buttons()
        self.control_panel.update_status(status_to_display)
        self.save_thread.quit()

    def _on_start_recording_clicked(self):
        """
        在开始录制前，强制将UI上完整的通道名称列表同步到DataProcessor。
        """
        # 1. 从 ControlPanel 获取当前所有通道的名称
        current_names = self.control_panel.get_channel_names()

        # 2. 将这个完整的列表发送给 DataProcessor
        #    这将覆盖掉 DataProcessor 中任何陈旧的状态
        self.data_processor.set_channel_names(current_names)

        # 3. 现在，命令 DataProcessor 开始录制
        self.data_processor.start_recording()

    def _on_acquisition_started(self):
        """当引导式采集开始时，动态创建并显示覆盖层"""
        print("UI notified: Acquisition has started.")

        # --- 核心修复：创建时不再指定父控件 (parent=None) ---
        self.guidance_overlay = GuidanceOverlay(parent=None)

        self.guidance_overlay.exit_clicked.connect(self.acquisition_controller.stop)

        self.acquisition_controller.update_state.connect(self.guidance_overlay.update_display)
        self.guidance_overlay.show_overlay()

        self.control_panel.start_rec_btn.setEnabled(False)
        self.control_panel.stop_rec_btn.setEnabled(False)
        #self.time_domain_widget.start_acq_btn.setEnabled(False)

    def _on_acquisition_finished(self):
        """当引导式采集结束时，销毁覆盖层并恢复UI"""
        print("UI notified: Acquisition has finished.")

        # --- 核心修复 3：安全地销毁 Overlay ---
        if hasattr(self, 'guidance_overlay') and self.guidance_overlay:
            # 断开所有连接，防止内存泄漏
            try:
                self.acquisition_controller.update_state.disconnect(self.guidance_overlay.update_display)
            except TypeError:
                pass  # 信号可能已经断开

            self.guidance_overlay.hide_overlay()
            self.guidance_overlay.deleteLater()  # 安全地删除对象
            self.guidance_overlay = None

        # --- 恢复按钮状态的逻辑保持不变 ---
        #self.time_domain_widget.start_acq_btn.setEnabled(True)
        self.update_ui_on_connection(self.is_session_running)

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

    def show_about_dialog(self):
        """显示程序的“关于”对话框"""
        about_dialog = QMessageBox(self)
        about_dialog.setWindowTitle("About ExGMP")

        # 设置左侧的Logo图标 (QPixmap用于显示图片)
        logo_pixmap = QPixmap(resource_path("icons/logo.png"))
        # 将其缩放到合适的大小，例如 64x64，并保持宽高比
        scaled_logo = logo_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        about_dialog.setIconPixmap(scaled_logo)

        # 设置右侧的文本内容 (支持HTML格式)
        about_dialog.setTextFormat(Qt.TextFormat.RichText)
        about_dialog.setText(
            "<h2>ExG Monitor Platform</h2>"
            "<p>Version 1.0</p>"
            "<p>An application for ExG data acquisition and analysis.</p>"
            "<p>Developed by BioSignal Link.</p>"
            "<p>&copy; 2025.10.16</p>"
        )

        about_dialog.exec()