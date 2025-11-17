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
    gain_changed = pyqtSignal(float)

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

        rates = [250, 500, 1000, 2000, 4000]
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

        channel_options = [2, 4, 6, 8]  # 例如：ADS1298 (2ch), ADS1299 (8ch)
        for num in channel_options:
            radio_button = QRadioButton(f"{num} Channels")
            self.channels_button_group.addButton(radio_button, num)
            channels_layout.addWidget(radio_button)
            if num == default_channels:
                radio_button.setChecked(True)

        channels_group.setLayout(channels_layout)
        # 当按钮被点击时，发射新信号
        self.channels_button_group.idClicked.connect(self.num_channels_changed)

        gain_group = QGroupBox("Gain")
        gain_layout = QVBoxLayout()
        self.gain_button_group = QButtonGroup(self)
        self.gain_button_group.setExclusive(True)

        # 定义增益选项 (值可以是浮点数)
        # ADS1298/99 支持 1, 2, 4, 6, 8, 12, 24
        gain_options = [12.0, 24.0]
        default_gain = 12.0  # 假设默认增益为12

        for gain in gain_options:
            # 使用 int(gain) 来避免在文本中显示 ".0"
            radio_button = QRadioButton(f"x{int(gain)}")
            # 【关键】: QButtonGroup 不直接支持浮点数ID, 我们通过一个技巧来处理
            # 我们可以将浮点数乘以10或100转为整数ID
            gain_id = int(gain * 10)
            self.gain_button_group.addButton(radio_button, gain_id)
            gain_layout.addWidget(radio_button)
            if gain == default_gain:
                radio_button.setChecked(True)

        gain_group.setLayout(gain_layout)
        # 当按钮ID被点击时，连接到一个新的处理函数
        self.gain_button_group.idClicked.connect(self._on_gain_id_clicked)

        # --- 每包帧数组 ---
        frames_group = QGroupBox("Frames Per Packet")
        frames_layout = QVBoxLayout()
        self.frames_button_group = QButtonGroup(self)
        self.frames_button_group.setExclusive(True)

        frame_options = [10, 50]
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
        main_layout.addWidget(gain_group)
        main_layout.addWidget(frames_group)

    def get_current_channels(self) -> int:
        """返回当前选中的通道数。"""
        # checkedId() 返回与选中按钮关联的整数ID，这正是我们需要的通道数
        return self.channels_button_group.checkedId()

    def _on_gain_id_clicked(self, gain_id: int):
        gain_float = float(gain_id) / 10.0
        self.gain_changed.emit(gain_float)

    def get_current_gain(self) -> float:
        """返回当前选中的增益值 (浮点数)"""
        gain_id = self.gain_button_group.checkedId()
        if gain_id != -1:  # -1 表示没有按钮被选中
            return float(gain_id) / 10.0
        return 12.0  # 返回一个默认值以防万一