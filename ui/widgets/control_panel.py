# In ui/widgets/control_panel.py
import time
from functools import partial
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QGroupBox,
                             QPushButton, QLabel, QCheckBox, QLineEdit,
                             QSpinBox, QDoubleSpinBox, QComboBox, QButtonGroup, QHBoxLayout)
from PyQt6.QtCore import pyqtSignal, pyqtSlot


class ControlPanel(QWidget):

    # add open mat file signal
    open_file_clicked = pyqtSignal()
    # --- Add signals for recording ---
    start_recording_clicked = pyqtSignal()
    stop_recording_clicked = pyqtSignal()
    add_marker_clicked = pyqtSignal(str)  # Signal will carry the marker text
    channel_name_changed = pyqtSignal(int, str)  # (channel_index, new_name)

    # 定义信号，让主窗口知道发生了什么
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
        self.is_connected = False
        self.num_channels = 8

        self.y_scales = []
        self.ch_checkboxes = []
        self.ch_scale_labels = []
        self.ch_name_edits = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # "Status & Statistics" GroupBox
        status_group = QGroupBox("Status & Statistics")
        status_layout = QVBoxLayout()

        self.status_lbl = QLabel("Status: Disconnected")
        self.pps_lbl = QLabel("Packets/sec: 0")
        self.kbs_lbl = QLabel("Data Rate: 0.0 KB/s")

        status_layout.addWidget(self.status_lbl)
        status_layout.addWidget(self.pps_lbl)
        status_layout.addWidget(self.kbs_lbl)
        status_group.setLayout(status_layout)

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

        # --- "Channel Settings" GroupBox (动态构建) ---
        self.ch_group = QGroupBox("Channel Settings")
        self.ch_layout = QGridLayout()
        self.ch_group.setLayout(self.ch_layout)

        # 显示和滤波
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
        layout.addWidget(status_group)
        layout.addWidget(rec_group)
        layout.addWidget(settings_group)
        layout.addWidget(self.ch_group)
        layout.addStretch()

        # --- 执行一次构建 ---
        self.reconfigure_channels(self.num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        """
        这个槽函数是核心。它会清空并根据新的通道数重建通道设置UI。
        它由 MainWindow 的 num_channels_changed 信号触发。
        """
        # 如果通道数未改变，且UI已经构建，则无需操作以避免闪烁
        if self.num_channels == num_channels and self.ch_checkboxes:
            return

        print(f"ControlPanel: Reconfiguring UI for {num_channels} channels.")
        self.num_channels = num_channels

        # 1. 清空旧的UI组件
        # 这个循环是安全地从布局中移除并删除所有旧控件的关键
        while self.ch_layout.count():
            item = self.ch_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # 2. 重置内部状态列表以匹配新的通道数
        self.y_scales = [200.0] * num_channels
        self.ch_checkboxes = []
        self.ch_scale_labels = []
        self.ch_name_edits = []

        # 3. 重新创建并添加新的UI组件
        for i in range(num_channels):
            checkbox = QCheckBox(checked=True)
            checkbox.setToolTip(f"Toggle visibility for Channel {i + 1}")
            # 使用 lambda 捕获当前的通道索引 'i'
            checkbox.stateChanged.connect(lambda state, ch=i: self.channel_visibility_changed.emit(ch, bool(state)))

            name_edit = QLineEdit(f"CH {i + 1}")
            # 使用 functools.partial 是连接带参数信号的另一种稳健方式
            name_edit.editingFinished.connect(partial(self._on_name_changed, i))

            scale_lbl = QLabel(f"Scale: {int(self.y_scales[i])}µV")

            zoom_in = QPushButton("+")
            zoom_in.setFixedWidth(30)  # 保持UI整洁
            zoom_in.clicked.connect(partial(self.adjust_scale, i, 0.8))

            zoom_out = QPushButton("-")
            zoom_out.setFixedWidth(30)
            zoom_out.clicked.connect(partial(self.adjust_scale, i, 1.25))

            # 将新创建的控件添加到网格布局中
            self.ch_layout.addWidget(checkbox, i, 0)
            self.ch_layout.addWidget(name_edit, i, 1)
            self.ch_layout.addWidget(scale_lbl, i, 2)
            self.ch_layout.addWidget(zoom_out, i, 3)
            self.ch_layout.addWidget(zoom_in, i, 4)

            # 将控件的引用保存到列表中，以便后续访问
            self.ch_checkboxes.append(checkbox)
            self.ch_scale_labels.append(scale_lbl)
            self.ch_name_edits.append(name_edit)

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
        is_connection_message = "Connected" in message or "已连接" in message
        is_disconnection_message = "Disconnected" in message or "已断开" in message or "连接错误" in message

        # 只更新文本，不再自己管理按钮状态
        self.status_lbl.setText(f"Status: {message}")

        if is_connection_message:
            self.is_connected = True
        elif is_disconnection_message:
            self.is_connected = False
            # 断开时重置统计数据
            self.pps_lbl.setText("Packets/sec: 0")
            self.kbs_lbl.setText("Data Rate: 0.0 KB/s")

    @pyqtSlot(int, int)
    def update_stats(self, packet_count, byte_count):
        # 如果控件不可见（很可能因为窗口正在关闭），则不执行任何操作。
        if not self.isVisible():
            return

        current_time = time.time()
        elapsed = current_time - self.last_stat_time
        if elapsed > 0:
            pps = packet_count / elapsed
            kbs = (byte_count / elapsed) / 1024
            self.pps_lbl.setText(f"Packets/sec: {pps:.1f}")
            self.kbs_lbl.setText(f"Data Rate: {kbs:.1f} KB/s")
        self.last_stat_time = current_time

    def adjust_scale(self, channel, factor):
        # Calculate the absolute new scale value
        new_scale = self.y_scales[channel] * factor

        # Check bounds
        if 1 < new_scale < 5000:
            self.y_scales[channel] = new_scale
            self.ch_scale_labels[channel].setText(f"Scale: {int(new_scale)}µV")
            # Emit the absolute new scale value
            self.channel_scale_changed.emit(channel, new_scale)
    # def adjust_scale(self, channel, factor):
    #     new_scale = self.y_scales[channel] * factor
    #     if 1 < new_scale < 5000:
    #         self.y_scales[channel] = new_scale
    #         self.ch_scale_labels[channel].setText(f"Scale: {int(new_scale)}µV")
    #         self.channel_scale_changed.emit(channel, new_scale)

    def _on_name_changed(self, channel_index):
        """当一个通道名称 QLineEdit 完成编辑时调用"""
        new_name = self.ch_name_edits[channel_index].text()
        self.channel_name_changed.emit(channel_index, new_name)
        print(f"Channel {channel_index + 1} name changed to: {new_name}")

    def get_channel_names(self):
        """一个公共方法，返回所有通道当前名称的列表"""
        return [edit.text() for edit in self.ch_name_edits]