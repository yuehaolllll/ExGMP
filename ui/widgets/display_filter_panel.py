# File: ui/widgets/display_filter_panel.py

from PyQt6.QtWidgets import (QWidget, QGridLayout, QLabel, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QComboBox, QPushButton, QVBoxLayout, QHBoxLayout)
from PyQt6.QtCore import pyqtSignal, Qt


class DisplayFilterPanel(QWidget):
    plot_duration_changed = pyqtSignal(int)
    filter_settings_changed = pyqtSignal(float, float)
    notch_filter_changed = pyqtSignal(bool, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # --- 辅助函数：统一 Label 样式 ---
        def create_row(label_text, widget):
            row_layout = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(90)  # 固定宽度确保对齐
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(lbl)
            row_layout.addWidget(widget)
            return row_layout

        # 1. Plot Duration
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(2, 30)
        self.duration_spinbox.setValue(5)
        self.duration_spinbox.setSuffix(" s")
        self.duration_spinbox.setMinimumHeight(32)
        main_layout.addLayout(create_row("Duration:", self.duration_spinbox))

        # 2. High-pass
        self.hp_spinbox = QDoubleSpinBox()
        self.hp_spinbox.setRange(0.0, 200.0)
        self.hp_spinbox.setValue(0.0)
        self.hp_spinbox.setSuffix(" Hz")
        self.hp_spinbox.setSingleStep(0.5)
        self.hp_spinbox.setMinimumHeight(32)
        main_layout.addLayout(create_row("High-pass:", self.hp_spinbox))

        # 3. Low-pass
        self.lp_spinbox = QDoubleSpinBox()
        self.lp_spinbox.setRange(0.0, 500.0)
        self.lp_spinbox.setValue(100.0)
        self.lp_spinbox.setSuffix(" Hz")
        self.lp_spinbox.setSingleStep(5.0)
        self.lp_spinbox.setMinimumHeight(32)
        main_layout.addLayout(create_row("Low-pass:", self.lp_spinbox))

        # 4. Notch Filter (改进版)
        # 不再使用 Label，直接用 Checkbox 作为开关文本，右侧放频率
        notch_layout = QHBoxLayout()

        self.notch_checkbox = QCheckBox("Enable Notch Filter")
        self.notch_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        # 让 Checkbox 占据左侧空间

        self.notch_freq_combo = QComboBox()
        self.notch_freq_combo.addItems(["50 Hz", "60 Hz"])
        self.notch_freq_combo.setFixedWidth(110)
        self.notch_freq_combo.setMinimumHeight(32)

        # 初始禁用 Combo，直到勾选
        self.notch_freq_combo.setEnabled(False)
        self.notch_checkbox.toggled.connect(self.notch_freq_combo.setEnabled)

        notch_layout.addWidget(self.notch_checkbox)
        notch_layout.addStretch()  # 中间弹簧
        notch_layout.addWidget(self.notch_freq_combo)

        main_layout.addLayout(notch_layout)

        main_layout.addSpacing(10)

        # 5. Apply 按钮
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.setObjectName("btnConnect")  # 蓝色实心样式
        self.apply_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_settings_btn.setFixedHeight(38)

        main_layout.addWidget(self.apply_settings_btn)
        main_layout.addStretch()

        self.apply_settings_btn.clicked.connect(self._on_apply_settings)

    def _on_apply_settings(self):
        duration = self.duration_spinbox.value()
        high_pass = self.hp_spinbox.value()
        low_pass = self.lp_spinbox.value()

        if high_pass >= low_pass and high_pass > 0:
            print("Warning: HP must be < LP")
            return

        self.plot_duration_changed.emit(duration)
        self.filter_settings_changed.emit(high_pass, low_pass)

        notch_enabled = self.notch_checkbox.isChecked()
        freq_text = self.notch_freq_combo.currentText()
        notch_freq = float(freq_text.split()[0])
        self.notch_filter_changed.emit(notch_enabled, notch_freq)