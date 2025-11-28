# File: ui/widgets/display_filter_panel.py

import sys
import os
from PyQt6.QtWidgets import (QWidget, QGridLayout, QLabel, QSpinBox, QFrame,
                             QDoubleSpinBox, QCheckBox, QComboBox, QPushButton, QVBoxLayout, QHBoxLayout,
                             QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QTimer


# --- 1. 路径处理函数 (确保打包后也能找到图片) ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class DisplayFilterPanel(QWidget):
    plot_duration_changed = pyqtSignal(int)
    filter_settings_changed = pyqtSignal(float, float)
    notch_filter_changed = pyqtSignal(bool, float)
    # 信号：发送 Y 轴缩放值 (0 = Auto, 其他值为固定的 +/- uV)
    vert_scale_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 2. 获取图标绝对路径并处理格式 ---
        icon_plus = resource_path(os.path.join("icons", "plus.svg")).replace("\\", "/")
        icon_minus = resource_path(os.path.join("icons", "minus.svg")).replace("\\", "/")
        icon_arrow_down = resource_path(os.path.join("icons", "drop_down.svg")).replace("\\", "/")

        # --- 3. 样式表 (注入路径) ---
        self.setStyleSheet(f"""
            /* SpinBox 主体 */
            QSpinBox, QDoubleSpinBox {{
                background-color: #F8F9FA;
                border: 1px solid #DADCE0;
                border-radius: 4px;
                padding-left: 8px;
                padding-right: 24px; 
                min-height: 32px;
                color: #3C4043;
                selection-background-color: #1A73E8;
            }}
            QSpinBox:hover, QDoubleSpinBox:hover {{
                border: 1px solid #1A73E8;
                background-color: #FFFFFF;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 2px solid #1A73E8;
                background-color: #FFFFFF;
            }}

            /* 按钮区域 */
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                width: 24px;
                background-color: transparent;
                border-left: 1px solid #DADCE0;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #E8F0FE;
            }}

            /* 上按钮 */
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-position: top right;
                border-top-right-radius: 4px;
                height: 16px;
                margin-bottom: 0px;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: url("{icon_plus}");
                width: 10px; height: 10px;
            }}

            /* 下按钮 */
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-position: bottom right;
                border-bottom-right-radius: 4px;
                height: 16px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: url("{icon_minus}");
                width: 10px; height: 10px;
            }}

            /* ComboBox */
            QComboBox {{
                border: 1px solid #DADCE0;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 30px;
                background-color: #F8F9FA;
                color: #3C4043;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }}
            QComboBox::down-arrow {{
                image: url("{icon_arrow_down}");
                width: 20px; height: 20px;
                border: none; 
            }}
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- Grid 布局 ---
        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(12)
        grid_layout.setHorizontalSpacing(10)

        # 1. Time Window
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(2, 60)
        self.duration_spinbox.setValue(5)
        self.duration_spinbox.setSuffix(" s")
        self._config_spinbox(self.duration_spinbox)
        self._add_row(grid_layout, 0, "Time Window:", self.duration_spinbox)

        # 2. Vertical Scale (Y轴幅度) ---
        self.scale_combo = QComboBox()
        # 定义常用刻度：Auto, 50uV, 100uV... 10000uV
        self.scale_options = ["Auto", "50 µV", "100 µV", "200 µV", "400 µV", "1000 µV", "10000 µV"]
        self.scale_combo.addItems(self.scale_options)
        self.scale_combo.setCurrentIndex(2)  # 默认选中 Auto
        self.scale_combo.setCurrentIndex(0)

        self.scale_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._add_row(grid_layout, 1, "Vert Scale:", self.scale_combo)

        # 3. High-pass
        self.hp_spinbox = QDoubleSpinBox()
        self.hp_spinbox.setRange(0.0, 100.0)
        self.hp_spinbox.setValue(0.5)
        self.hp_spinbox.setSuffix(" Hz")
        self.hp_spinbox.setSingleStep(0.1)
        self.hp_spinbox.setDecimals(2)
        self._config_spinbox(self.hp_spinbox)
        self._add_row(grid_layout, 2, "High-pass:", self.hp_spinbox)

        # 4. Low-pass
        self.lp_spinbox = QDoubleSpinBox()
        self.lp_spinbox.setRange(10.0, 1000.0)
        self.lp_spinbox.setValue(100.0)
        self.lp_spinbox.setSuffix(" Hz")
        self.lp_spinbox.setSingleStep(5.0)
        self.lp_spinbox.setDecimals(1)
        self._config_spinbox(self.lp_spinbox)
        self._add_row(grid_layout, 3, "Low-pass:", self.lp_spinbox)

        main_layout.addLayout(grid_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #E0E0E0; margin: 5px 0;")
        line.setFixedHeight(1)
        main_layout.addWidget(line)

        # --- Notch Filter ---
        notch_container = QHBoxLayout()
        notch_container.setContentsMargins(0, 0, 0, 0)
        notch_container.setSpacing(5)

        self.notch_checkbox = QCheckBox("Notch Filter")
        self.notch_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notch_checkbox.setStyleSheet("font-weight: 500; color: #3C4043;")

        self.notch_freq_combo = QComboBox()
        self.notch_freq_combo.addItems(["50 Hz", "60 Hz"])
        self.notch_freq_combo.setFixedWidth(85)
        self.notch_freq_combo.setEnabled(False)

        self.notch_checkbox.toggled.connect(self.notch_freq_combo.setEnabled)

        notch_container.addWidget(self.notch_checkbox)
        notch_container.addStretch()
        notch_container.addWidget(self.notch_freq_combo)

        main_layout.addLayout(notch_container)
        main_layout.addSpacing(5)

        # --- Apply 按钮 ---
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_settings_btn.setFixedHeight(36)
        self.apply_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A73E8; 
                color: white; 
                border-radius: 4px;
                font-weight: bold;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1557B0; }
            QPushButton:pressed { background-color: #0D47A1; }
        """)

        main_layout.addWidget(self.apply_settings_btn)
        main_layout.addStretch()

        self.apply_settings_btn.clicked.connect(self._on_apply_settings)

    def _config_spinbox(self, box):
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _add_row(self, layout, row, text, widget):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color: #5F6368; font-size: 13px;")
        layout.addWidget(lbl, row, 0)
        layout.addWidget(widget, row, 1)

    def sizeHint(self):
        # 稍微增加一点高度以容纳新的一行
        return QSize(280, 300)

    def _on_apply_settings(self):
        duration = self.duration_spinbox.value()
        high_pass = self.hp_spinbox.value()
        low_pass = self.lp_spinbox.value()

        if high_pass >= low_pass and low_pass > 0:
            print(f"Filter Error: HP >= LP")
            self.hp_spinbox.setStyleSheet(self.styleSheet() +
                                          "QDoubleSpinBox { border: 1px solid #D32F2F; background-color: #FCE8E6; }")
            return
        else:
            self.hp_spinbox.setStyleSheet("")

        self.plot_duration_changed.emit(duration)
        self.filter_settings_changed.emit(high_pass, low_pass)

        # --- 处理 Scale 变化 ---
        scale_text = self.scale_combo.currentText()
        if "Auto" in scale_text:
            scale_val = 0  # 0 代表自动
        else:
            # 提取字符串中的数字，例如 "200 µV" -> 200
            try:
                scale_val = int(scale_text.split()[0])
            except ValueError:
                scale_val = 0

        self.vert_scale_changed.emit(scale_val)
        # ---------------------------

        notch_enabled = self.notch_checkbox.isChecked()
        freq_text = self.notch_freq_combo.currentText()
        notch_freq = float(freq_text.split()[0])
        self.notch_filter_changed.emit(notch_enabled, notch_freq)

        original_text = self.apply_settings_btn.text()
        self.apply_settings_btn.setText("Applied!")
        self.apply_settings_btn.setStyleSheet(
            "background-color: #2E7D32; color: white; border-radius: 4px; font-weight: bold; border: none;")
        QTimer.singleShot(1000, lambda: self._reset_btn(original_text))

    def _reset_btn(self, text):
        self.apply_settings_btn.setText(text)
        self.apply_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A73E8; 
                color: white; 
                border-radius: 4px;
                font-weight: bold;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1557B0; }
            QPushButton:pressed { background-color: #0D47A1; }
        """)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.apply_settings_btn.click()
        else:
            super().keyPressEvent(event)