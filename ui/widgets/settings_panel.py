# File: ui/widgets/settings_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QGroupBox, QRadioButton, QButtonGroup, QScrollArea)
from PyQt6.QtCore import pyqtSignal, Qt, QSize


class SettingsPanel(QWidget):
    """
    一个包含所有设置选项的自定义面板，用于嵌入到菜单中。
    """
    sample_rate_changed = pyqtSignal(int)
    frames_per_packet_changed = pyqtSignal(int)
    num_channels_changed = pyqtSignal(int)
    gain_changed = pyqtSignal(float)

    def __init__(self, default_rate=1000, default_frames=50, default_channels=8, parent=None):
        super().__init__(parent)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- 1. 通道数 (横向排列) ---
        channels_group = QGroupBox("Channels")
        channels_layout = QHBoxLayout()  # 改用水平布局
        channels_layout.setContentsMargins(10, 20, 10, 10)  # 顶部留空间给标题

        self.channels_button_group = QButtonGroup(self)

        # 定义选项
        channel_options = [2, 4, 6, 8]
        for num in channel_options:
            radio_button = QRadioButton(f"{num}")
            # 稍微让文字居中一点
            radio_button.setStyleSheet("padding-left: 5px;")
            self.channels_button_group.addButton(radio_button, num)
            channels_layout.addWidget(radio_button)
            if num == default_channels:
                radio_button.setChecked(True)

        channels_group.setLayout(channels_layout)
        self.channels_button_group.idClicked.connect(self.num_channels_changed)
        main_layout.addWidget(channels_group)

        # --- 2. 采样率 (网格排列) ---
        # 7个选项垂直排太长了，改成 2列网格布局
        rate_group = QGroupBox("Sample Rate")
        rate_layout = QGridLayout()
        rate_layout.setContentsMargins(10, 20, 10, 10)
        rate_layout.setVerticalSpacing(8)

        self.rate_button_group = QButtonGroup(self)

        rates = [250, 500, 1000, 2000, 4000, 8000, 16000]
        # 使用 enumerate 和取模运算来排布
        for i, rate in enumerate(rates):
            radio_button = QRadioButton(f"{rate} Hz")
            self.rate_button_group.addButton(radio_button, rate)

            row = i // 2  # 2列布局
            col = i % 2
            rate_layout.addWidget(radio_button, row, col)

            if rate == default_rate:
                radio_button.setChecked(True)

        rate_group.setLayout(rate_layout)
        self.rate_button_group.idClicked.connect(self.sample_rate_changed)
        main_layout.addWidget(rate_group)

        # --- 3. 高级设置 (Gain & Frames 并排) ---
        # 将这两个小项合并到一行，节省大量垂直空间
        advanced_layout = QHBoxLayout()
        advanced_layout.setSpacing(15)

        # 3a. Gain Group
        gain_group = QGroupBox("Gain")
        gain_inner_layout = QVBoxLayout()
        gain_inner_layout.setContentsMargins(10, 15, 10, 10)

        self.gain_button_group = QButtonGroup(self)
        gain_options = [12.0, 24.0]
        default_gain = 12.0

        for gain in gain_options:
            radio_button = QRadioButton(f"x{int(gain)}")
            gain_id = int(gain * 10)
            self.gain_button_group.addButton(radio_button, gain_id)
            gain_inner_layout.addWidget(radio_button)
            if gain == default_gain:
                radio_button.setChecked(True)

        gain_group.setLayout(gain_inner_layout)
        self.gain_button_group.idClicked.connect(self._on_gain_id_clicked)
        advanced_layout.addWidget(gain_group)

        # 3b. Frames Group
        frames_group = QGroupBox("Packet Size")  # 简化标题
        frames_inner_layout = QVBoxLayout()
        frames_inner_layout.setContentsMargins(10, 15, 10, 10)

        self.frames_button_group = QButtonGroup(self)
        frame_options = [10, 50]

        for frames in frame_options:
            radio_button = QRadioButton(f"{frames} frames")
            self.frames_button_group.addButton(radio_button, frames)
            frames_inner_layout.addWidget(radio_button)
            if frames == default_frames:
                radio_button.setChecked(True)

        frames_group.setLayout(frames_inner_layout)
        self.frames_button_group.idClicked.connect(self.frames_per_packet_changed)
        advanced_layout.addWidget(frames_group)

        main_layout.addLayout(advanced_layout)

        # 底部弹簧
        main_layout.addStretch()

    # --- 辅助方法 ---
    def _on_gain_id_clicked(self, gain_id: int):
        gain_float = float(gain_id) / 10.0
        self.gain_changed.emit(gain_float)

    # --- Public Getters ---
    def get_current_channels(self) -> int:
        return self.channels_button_group.checkedId()

    def get_current_sample_rate(self) -> int:
        return self.rate_button_group.checkedId()

    def get_current_frames(self) -> int:
        return self.frames_button_group.checkedId()

    def get_current_gain(self) -> float:
        gain_id = self.gain_button_group.checkedId()
        if gain_id != -1:
            return float(gain_id) / 10.0
        return 12.0

    def sizeHint(self):
        # 限制面板的建议宽度，让菜单更紧凑
        return QSize(300, 450)