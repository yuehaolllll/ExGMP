from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QRadioButton, QButtonGroup
from PyQt6.QtCore import pyqtSignal


class SettingsPanel(QWidget):
    """
    一个包含所有设置选项的自定义面板，用于嵌入到菜单中。
    """
    # 定义信号，以便在设置更改时通知 MainWindow
    sample_rate_changed = pyqtSignal(int)
    frames_per_packet_changed = pyqtSignal(int)
    num_channels_changed = pyqtSignal(int)

    def __init__(self, default_rate=1000, default_frames=50, default_channels=8, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)  # 调整边距以适应菜单
        main_layout.setSpacing(10)

        # --- 采样率组 ---
        rate_group = QGroupBox("Sample Rate")
        rate_layout = QVBoxLayout()
        self.rate_button_group = QButtonGroup(self)
        self.rate_button_group.setExclusive(True)

        rates = [250, 500, 1000, 2000]
        for rate in rates:
            radio_button = QRadioButton(f"{rate} Hz")
            # 将 rate 值与按钮关联
            self.rate_button_group.addButton(radio_button, rate)
            rate_layout.addWidget(radio_button)
            if rate == default_rate:
                radio_button.setChecked(True)

        rate_group.setLayout(rate_layout)
        # 当按钮组中的按钮被点击时，发射信号
        self.rate_button_group.idClicked.connect(self.sample_rate_changed)

        channels_group = QGroupBox("Number of Channels")
        channels_layout = QVBoxLayout()
        self.channels_button_group = QButtonGroup(self)
        self.channels_button_group.setExclusive(True)

        channel_options = [2, 8]  # 例如：ADS1298 (2ch), ADS1299 (8ch)
        for num in channel_options:
            radio_button = QRadioButton(f"{num} Channels")
            self.channels_button_group.addButton(radio_button, num)
            channels_layout.addWidget(radio_button)
            if num == default_channels:
                radio_button.setChecked(True)

        channels_group.setLayout(channels_layout)
        # 当按钮被点击时，发射新信号
        self.channels_button_group.idClicked.connect(self.num_channels_changed)

        # --- 每包帧数组 ---
        frames_group = QGroupBox("Frames Per Packet")
        frames_layout = QVBoxLayout()
        self.frames_button_group = QButtonGroup(self)
        self.frames_button_group.setExclusive(True)

        frame_options = [10, 50, 100]
        for frames in frame_options:
            radio_button = QRadioButton(f"{frames}")
            self.frames_button_group.addButton(radio_button, frames)
            frames_layout.addWidget(radio_button)
            if frames == default_frames:
                radio_button.setChecked(True)

        frames_group.setLayout(frames_layout)
        self.frames_button_group.idClicked.connect(self.frames_per_packet_changed)

        # 将所有组添加到主布局
        main_layout.addWidget(channels_group)
        main_layout.addWidget(rate_group)
        main_layout.addWidget(frames_group)

    def get_current_channels(self) -> int:
        """返回当前选中的通道数。"""
        # checkedId() 返回与选中按钮关联的整数ID，这正是我们需要的通道数
        return self.channels_button_group.checkedId()