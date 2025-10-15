# In ui/widgets/control_panel.py
import time
from functools import partial
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QGroupBox,
                             QPushButton, QLabel, QCheckBox, QLineEdit,
                             QSpinBox, QDoubleSpinBox, QComboBox, QButtonGroup, QHBoxLayout)
from PyQt6.QtCore import pyqtSignal

NUM_CHANNELS = 8
PACKET_SIZE = 1354


class ControlPanel(QWidget):

    # add open mat file signal
    open_file_clicked = pyqtSignal()
    # --- Add signals for recording ---
    start_recording_clicked = pyqtSignal()
    stop_recording_clicked = pyqtSignal()
    add_marker_clicked = pyqtSignal(str)  # Signal will carry the marker text

    # 定义信号，让主窗口知道发生了什么
    connect_clicked = pyqtSignal()
    disconnect_clicked = pyqtSignal()
    channel_visibility_changed = pyqtSignal(int, bool)
    channel_scale_changed = pyqtSignal(int, float)
    # plot length
    plot_duration_changed = pyqtSignal(int)
    # freq param
    filter_settings_changed = pyqtSignal(float, float)
    notch_filter_changed = pyqtSignal(bool, float)  # (enabled, frequency)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_stat_time = time.time()
        self.y_scales = [200.0] * NUM_CHANNELS
        self.is_connected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 连接控制
        conn_group = QGroupBox("Connection")
        conn_layout = QGridLayout()
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect", enabled=False)
        #self.open_btn = QPushButton("Open File")
        self.status_lbl = QLabel("Status: Disconnected")
        self.connect_btn.clicked.connect(self.connect_clicked.emit)
        self.disconnect_btn.clicked.connect(self.disconnect_clicked.emit)
        #self.open_btn.clicked.connect(self.open_file_clicked.emit)

        conn_layout.addWidget(self.connect_btn, 0, 0)
        conn_layout.addWidget(self.disconnect_btn, 0, 1)
        #conn_layout.addWidget(self.open_btn, 1, 0, 1, 2)
        conn_layout.addWidget(self.status_lbl, 1, 0, 1, 2)
        conn_group.setLayout(conn_layout)

        # 记录
        rec_group = QGroupBox("Recording")
        rec_layout = QGridLayout()
        self.start_rec_btn = QPushButton("Start Recording")
        self.stop_rec_btn = QPushButton("Stop Recording")
        self.marker_input = QLineEdit("Marker Label")
        self.add_marker_btn = QPushButton("Add Marker")
        self.open_btn = QPushButton(" Open File")

        # Initially, recording buttons are disabled until connection is established
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(False)
        self.add_marker_btn.setEnabled(False)
        self.open_btn = QPushButton("Open File")

        self.start_rec_btn.clicked.connect(self._on_start_recording)
        self.stop_rec_btn.clicked.connect(self._on_stop_recording)
        self.add_marker_btn.clicked.connect(self._on_add_marker)
        self.open_btn.clicked.connect(self.open_file_clicked.emit)

        rec_layout.addWidget(self.start_rec_btn, 0, 0)
        rec_layout.addWidget(self.stop_rec_btn, 0, 1)
        rec_layout.addWidget(self.marker_input, 1, 0)
        rec_layout.addWidget(self.add_marker_btn, 1, 1)
        rec_layout.addWidget(self.open_btn, 2, 0, 1, 2)
        rec_group.setLayout(rec_layout)

        # 通道设置
        ch_group = QGroupBox("Channel Settings")
        ch_layout = QGridLayout()
        self.ch_checkboxes = []
        self.ch_scale_labels = []
        for i in range(NUM_CHANNELS):
            checkbox = QCheckBox(f"CH {i + 1}", checked=True)
            checkbox.stateChanged.connect(lambda state, ch=i: self.channel_visibility_changed.emit(ch, bool(state)))
            scale_lbl = QLabel(f"Scale: {int(self.y_scales[i])}µV")
            zoom_in = QPushButton("+")
            zoom_out = QPushButton("-")
            zoom_in.clicked.connect(partial(self.adjust_scale, i, 0.8))
            zoom_out.clicked.connect(partial(self.adjust_scale, i, 1.25))
            ch_layout.addWidget(checkbox, i, 0)
            ch_layout.addWidget(scale_lbl, i, 1)
            ch_layout.addWidget(zoom_out, i, 2)
            ch_layout.addWidget(zoom_in, i, 3)
            self.ch_checkboxes.append(checkbox)
            self.ch_scale_labels.append(scale_lbl)
        ch_group.setLayout(ch_layout)

        # 统计
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        self.pps_lbl = QLabel("Packets/sec: 0")
        self.kbs_lbl = QLabel("Data Rate: 0.0 KB/s")
        stats_layout.addWidget(self.pps_lbl)
        stats_layout.addWidget(self.kbs_lbl)
        stats_group.setLayout(stats_layout)

        #
        settings_group = QGroupBox("Display & Filter")
        settings_layout = QGridLayout()

        # 绘图时长设置
        settings_layout.addWidget(QLabel("Plot Duration (s):"), 0, 0)
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(2, 30)  # 允许2到30秒
        self.duration_spinbox.setValue(5)  # 默认5秒
        self.duration_spinbox.setSuffix(" s")
        settings_layout.addWidget(self.duration_spinbox, 0, 1)

        # 高通滤波设置
        settings_layout.addWidget(QLabel("High-pass (Hz):"), 1, 0)
        self.hp_spinbox = QDoubleSpinBox()
        self.hp_spinbox.setRange(0.0, 200.0)
        self.hp_spinbox.setValue(0.0)  # 默认1Hz
        self.hp_spinbox.setSuffix(" Hz")
        self.hp_spinbox.setDecimals(1)
        self.hp_spinbox.setSingleStep(0.5)
        settings_layout.addWidget(self.hp_spinbox, 1, 1)

        # 低通滤波设置
        settings_layout.addWidget(QLabel("Low-pass (Hz):"), 2, 0)
        self.lp_spinbox = QDoubleSpinBox()
        self.lp_spinbox.setRange(0.0, 500.0)  # 最高到奈奎斯特频率的一半
        self.lp_spinbox.setValue(100.0)  # 默认50Hz
        self.lp_spinbox.setSuffix(" Hz")
        self.lp_spinbox.setDecimals(1)
        self.lp_spinbox.setSingleStep(5.0)
        settings_layout.addWidget(self.lp_spinbox, 2, 1)

        # 陷波滤波
        self.notch_checkbox = QCheckBox("Enable Notch Filter")
        settings_layout.addWidget(self.notch_checkbox, 3, 0)
        self.notch_freq_combo = QComboBox()
        self.notch_freq_combo.addItems(["50 Hz", "60 Hz"])
        settings_layout.addWidget(self.notch_freq_combo, 3, 1)

        # 应用按钮
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.clicked.connect(self._on_apply_settings)
        settings_layout.addWidget(self.apply_settings_btn, 4, 0, 1, 2)

        settings_group.setLayout(settings_layout)

        # 将所有 GroupBox 添加到主布局中
        layout.addWidget(conn_group)
        layout.addWidget(rec_group)
        layout.addWidget(settings_group)
        layout.addWidget(ch_group)
        layout.addWidget(stats_group)
        layout.addStretch()

    def _on_sample_rate_selected(self, button):
        # 从按钮组获取与被点击按钮关联的ID（即采样率）
        rate = self.rate_button_group.id(button)
        self.sample_rate_changed.emit(rate)
        print(f"UI Event: Sample rate changed to {rate} Hz.")

    def _on_apply_settings(self):
        # 读取控件的当前值
        duration = self.duration_spinbox.value()
        high_pass = self.hp_spinbox.value()
        low_pass = self.lp_spinbox.value()

        # 简单的验证
        if high_pass >= low_pass and high_pass > 0:
            print("Warning: High-pass frequency must be lower than low-pass frequency.")
            return

        # 发射信号
        self.plot_duration_changed.emit(duration)
        self.filter_settings_changed.emit(high_pass, low_pass)
        notch_enabled = self.notch_checkbox.isChecked()
        freq_text = self.notch_freq_combo.currentText()  # "50 Hz" or "60 Hz"
        notch_freq = float(freq_text.split()[0])  # 提取数字 50.0 or 60.0
        self.notch_filter_changed.emit(notch_enabled, notch_freq)

        print(
            f"Settings Applied: Duration={duration}s, HP={high_pass}Hz, LP={low_pass}Hz, Notch={'On' if notch_enabled else 'Off'} @ {notch_freq}Hz")

    def _on_start_recording(self):
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(True)
        self.add_marker_btn.setEnabled(True)
        self.status_lbl.setText("Status: Recording...")
        self.start_recording_clicked.emit()

    def _on_stop_recording(self):
        # 禁用所有录制相关的按钮，直到我们收到保存完成的信号
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(False)
        self.add_marker_btn.setEnabled(False)

        self.status_lbl.setText("Status: Saving file...")
        self.stop_recording_clicked.emit()

    def reset_recording_buttons(self):
        """
        这个方法将在文件保存完成后被外部调用，
        以安全地重置录制按钮的状态。
        """
        is_ready_to_record = self.is_connected  # 只有在连接状态下才能开始新录制
        self.start_rec_btn.setEnabled(is_ready_to_record)
        self.stop_rec_btn.setEnabled(False)
        # Marker 按钮应该在下一次录制开始时才启用
        self.add_marker_btn.setEnabled(False)

    def _on_add_marker(self):
        marker_text = self.marker_input.text()
        if marker_text:
            self.add_marker_clicked.emit(marker_text)
            # Optional: clear input after adding
            # self.marker_input.clear()

    def update_status(self, message):
        """
        这个函数现在只负责显示消息，并根据【特定】消息更新连接状态。
        """
        self.status_lbl.setText(f"Status: {message}")

        # --- 关键修复：只有在收到明确的连接/断开消息时，才更新 is_connected 状态 ---
        is_connection_message = "Connected" in message or "已连接" in message
        is_disconnection_message = "Disconnected" in message or "已断开" in message or "连接错误" in message

        if is_connection_message:
            self.is_connected = True
        elif is_disconnection_message:
            self.is_connected = False
        # 如果是其他消息 (如 "Saving file...", "File saved..."),
        # 我们【不改变】self.is_connected 的当前值。

        # --- 现在，根据【可靠的】is_connected 状态来更新所有按钮 ---
        self.connect_btn.setEnabled(not self.is_connected)
        self.disconnect_btn.setEnabled(self.is_connected)

        # 只有在【未处于录制中】时，才根据连接状态更新录制按钮
        # 我们通过检查 Stop 按钮的状态来判断是否在录制
        if not self.stop_rec_btn.isEnabled():
            self.start_rec_btn.setEnabled(self.is_connected)

        # "Open File" 按钮始终可用
        self.open_btn.setEnabled(True)

        if not self.is_connected:
            # 只有在真正断开连接时，才重置这些状态
            self.pps_lbl.setText("Packets/sec: 0")
            self.kbs_lbl.setText("Data Rate: 0.0 KB/s")
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)

    def update_stats(self, packet_count):
        current_time = time.time(); elapsed = current_time - self.last_stat_time
        if elapsed > 0:
            pps = packet_count / elapsed
            kbs = (packet_count * PACKET_SIZE) / elapsed / 1024
            self.pps_lbl.setText(f"Packets/sec: {pps:.1f}")
            self.kbs_lbl.setText(f"Data Rate: {kbs:.1f} KB/s")
        self.last_stat_time = current_time

    def adjust_scale(self, channel, factor):
        new_scale = self.y_scales[channel] * factor
        if 1 < new_scale < 5000:
            self.y_scales[channel] = new_scale
            self.ch_scale_labels[channel].setText(f"Scale: {int(new_scale)}µV")
            self.channel_scale_changed.emit(channel, new_scale)