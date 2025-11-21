# File: ui/widgets/display_filter_panel.py

from PyQt6.QtWidgets import (QWidget, QGridLayout, QLabel, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QComboBox, QPushButton)
from PyQt6.QtCore import pyqtSignal


class DisplayFilterPanel(QWidget):
    """
    一个独立的面板，用于控制绘图时长和数字滤波器设置。
    """
    # 1. 定义本面板需要向外发射的信号
    plot_duration_changed = pyqtSignal(int)
    filter_settings_changed = pyqtSignal(float, float)
    notch_filter_changed = pyqtSignal(bool, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 2. 将原来 ControlPanel 中创建 Display & Filter GroupBox 的代码 "搬" 过来
        settings_layout = QGridLayout(self)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(8)

        # 绘图时长设置
        settings_layout.addWidget(QLabel("Plot Duration (s):"), 0, 0)
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(2, 30)
        self.duration_spinbox.setValue(5)
        self.duration_spinbox.setSuffix(" s")
        settings_layout.addWidget(self.duration_spinbox, 0, 1)

        # 高通滤波设置
        settings_layout.addWidget(QLabel("High-pass (Hz):"), 1, 0)
        self.hp_spinbox = QDoubleSpinBox()
        self.hp_spinbox.setRange(0.0, 200.0)
        self.hp_spinbox.setValue(0.0)
        self.hp_spinbox.setSuffix(" Hz")
        self.hp_spinbox.setDecimals(1)
        self.hp_spinbox.setSingleStep(0.5)
        settings_layout.addWidget(self.hp_spinbox, 1, 1)

        # 低通滤波设置
        settings_layout.addWidget(QLabel("Low-pass (Hz):"), 2, 0)
        self.lp_spinbox = QDoubleSpinBox()
        self.lp_spinbox.setRange(0.0, 500.0)
        self.lp_spinbox.setValue(100.0)
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
        settings_layout.addWidget(self.apply_settings_btn, 4, 0, 1, 2)

        # 3. 连接 "Apply" 按钮的点击事件
        self.apply_settings_btn.clicked.connect(self._on_apply_settings)

    def _on_apply_settings(self):
        duration = self.duration_spinbox.value()
        high_pass = self.hp_spinbox.value()
        low_pass = self.lp_spinbox.value()

        if high_pass >= low_pass and high_pass > 0:
            print("Warning: High-pass frequency must be lower than low-pass frequency.")
            return

        # 发射信号
        self.plot_duration_changed.emit(duration)
        self.filter_settings_changed.emit(high_pass, low_pass)

        notch_enabled = self.notch_checkbox.isChecked()
        freq_text = self.notch_freq_combo.currentText()
        notch_freq = float(freq_text.split()[0])
        self.notch_filter_changed.emit(notch_enabled, notch_freq)

        print(
            f"Settings Applied: Duration={duration}s, HP={high_pass}Hz, LP={low_pass}Hz, Notch={'On' if notch_enabled else 'Off'} @ {notch_freq}Hz")