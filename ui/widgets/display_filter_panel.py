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

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 2. 获取图标绝对路径并处理格式 ---
        # Qt 样式表 (QSS) 即使在 Windows 上也强制要求使用正斜杠 '/'
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

            /* 上按钮 (使用 plus.svg) */
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-position: top right;
                border-top-right-radius: 4px;
                height: 16px;
                margin-bottom: 0px;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: url("{icon_plus}");
                width: 10px; height: 10px; /* 根据 SVG 实际大小微调 */
            }}

            /* 下按钮 (使用 minus.svg) */
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
            /* 下拉箭头也暂时用 minus 或者你需要单独找一个 arrow_down.svg */
            /* 这里为了统一样式，建议还是用 CSS 画一个简单的三角，或者你有 arrow.svg */
            QComboBox::down-arrow {{
                image: url("{icon_arrow_down}");
                width: 20px; height: 20px; /* 这里的尺寸决定图标大小 */
                
                /* 清除之前的边框绘图代码 */
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

        # 2. High-pass
        self.hp_spinbox = QDoubleSpinBox()
        self.hp_spinbox.setRange(0.0, 100.0)
        self.hp_spinbox.setValue(0.5)
        self.hp_spinbox.setSuffix(" Hz")
        self.hp_spinbox.setSingleStep(0.1)
        self.hp_spinbox.setDecimals(2)
        self._config_spinbox(self.hp_spinbox)
        self._add_row(grid_layout, 1, "High-pass:", self.hp_spinbox)

        # 3. Low-pass
        self.lp_spinbox = QDoubleSpinBox()
        self.lp_spinbox.setRange(10.0, 1000.0)
        self.lp_spinbox.setValue(100.0)
        self.lp_spinbox.setSuffix(" Hz")
        self.lp_spinbox.setSingleStep(5.0)
        self.lp_spinbox.setDecimals(1)
        self._config_spinbox(self.lp_spinbox)
        self._add_row(grid_layout, 2, "Low-pass:", self.lp_spinbox)

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
        # 这里需要去掉 main.py 全局样式对 checkbox 的影响，或者设置一个简单的样式
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
        return QSize(280, 270)

    def _on_apply_settings(self):
        duration = self.duration_spinbox.value()
        high_pass = self.hp_spinbox.value()
        low_pass = self.lp_spinbox.value()

        if high_pass >= low_pass and low_pass > 0:
            print(f"Filter Error: HP >= LP")
            # 错误样式：保留 QSS 结构，只改背景和边框
            self.hp_spinbox.setStyleSheet(self.styleSheet() +
                                          "QDoubleSpinBox { border: 1px solid #D32F2F; background-color: #FCE8E6; }")
            return
        else:
            # 恢复默认样式，重新设置整个 styleSheet 是最安全的做法
            # 或者简单调用 update()，但 PyQt 样式覆盖比较顽固
            # 这里我们简单重置
            self.hp_spinbox.setStyleSheet("")

        self.plot_duration_changed.emit(duration)
        self.filter_settings_changed.emit(high_pass, low_pass)

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