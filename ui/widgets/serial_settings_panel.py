# File: ui/widgets/serial_settings_panel.py

import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                             QPushButton, QLabel, QFormLayout, QStyle)
import serial.tools.list_ports
from PyQt6.QtCore import Qt


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SerialSettingsPanel(QWidget):
    """
    一个用于配置串口参数的UI面板。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 1. 路径获取与调试 ---
        # 获取绝对路径 (使用你确认正确的 drop_down.svg)
        raw_path = resource_path(os.path.join("icons", "drop_down.svg"))

        if not os.path.exists(raw_path):
            print(f"Warning: Icon not found at {raw_path}")

        # Windows路径修正
        icon_arrow_down = raw_path.replace("\\", "/")

        print(f"SerialPanel Icon Path: {icon_arrow_down}")

        # --- 2. 样式表优化 ---
        self.setStyleSheet(f"""
            /* 面板背景 */
            SerialSettingsPanel {{
                background-color: #F8F9FA; 
                border-radius: 6px;
                border: 1px solid #E8EAED;
            }}

            QLabel {{ color: #5F6368; font-weight: 500; }}

            /* 针对该面板下的所有 ComboBox */
            QComboBox {{
                background-color: #FFFFFF;
                border: 1px solid #DADCE0;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 32px;
                color: #3C4043;
            }}

            /* 鼠标悬停在整个输入框时：边框变蓝 */
            QComboBox:hover {{ 
                border: 1px solid #1A73E8; 
            }}

            /* 下拉时：底部直角 */
            QComboBox:on {{
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }}

            /* --- 交互核心：下拉按钮区域 --- */
            QComboBox::drop-down {{
                border: none; /* 默认无边框 */
                width: 24px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
                background: transparent; /* 默认透明 */
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}

            /* 【新增】鼠标悬停在箭头区域时：背景变淡蓝，加左分割线 */
            QComboBox::drop-down:hover {{
                background-color: #E8F0FE; /* 交互变色 */
                border-left: 1px solid #DADCE0; /* 增加分割线感 */
            }}

            /* 【核心】强制使用 SVG 图标 */
            QComboBox::down-arrow {{
                image: url("{icon_arrow_down}"); 
                width: 20px; height: 20px; /* 调整大小适配 */
                border: none; 
            }}

            /* 箭头在悬停时稍微位移一点点(可选，增加动感，这里暂不加以免闪烁) */

            /* 刷新按钮 */
            QPushButton#btnRefresh {{
                background-color: #FFFFFF;
                border: 1px solid #DADCE0;
                border-radius: 4px;
            }}
            QPushButton#btnRefresh:hover {{
                background-color: #E8F0FE; /* 悬停也变淡蓝，风格统一 */
                border: 1px solid #1A73E8;
            }}
            QPushButton#btnRefresh:pressed {{
                background-color: #D2E3FC;
            }}
        """)

        layout = QFormLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # --- COM 端口 ---
        self.com_port_combo = QComboBox()
        self.com_port_combo.setMinimumHeight(32)
        self.com_port_combo.setObjectName("SerialCombo")

        com_layout = QHBoxLayout()
        com_layout.setSpacing(8)
        com_layout.addWidget(self.com_port_combo, stretch=1)

        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_btn.setObjectName("btnRefresh")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh Serial Ports")
        self.refresh_btn.clicked.connect(self.refresh_com_ports)

        com_layout.addWidget(self.refresh_btn)

        # --- 波特率选择 ---
        self.baud_rate_combo = QComboBox()
        self.baud_rate_combo.setMinimumHeight(32)
        self.baud_rate_combo.setObjectName("SerialCombo")

        common_baud_rates = ["9600", "19200", "38400", "57600", "115200",
                             "230400", "460800", "921600", "1000000", "2000000"]
        self.baud_rate_combo.addItems(common_baud_rates)
        self.baud_rate_combo.setEditable(True)
        self.baud_rate_combo.setCurrentText("921600")

        # 修复 Editable ComboBox 的内部样式
        self.baud_rate_combo.lineEdit().setStyleSheet("border: none; background: transparent; color: #3C4043;")

        lbl_port = QLabel("Port:")
        lbl_port.setBuddy(self.com_port_combo)
        layout.addRow(lbl_port, com_layout)

        lbl_baud = QLabel("Baud:")
        lbl_baud.setBuddy(self.baud_rate_combo)
        layout.addRow(lbl_baud, self.baud_rate_combo)

        self.refresh_com_ports()

    def refresh_com_ports(self):
        self.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()

        if not ports:
            self.com_port_combo.addItem("No ports found")
            self.com_port_combo.setEnabled(False)
        else:
            sorted_ports = sorted(ports, key=lambda p: p.device)
            for port in sorted_ports:
                display_text = f"{port.device}"
                if port.description and port.description != "n/a":
                    display_text += f" ({port.description})"
                self.com_port_combo.addItem(display_text, port.device)
            self.com_port_combo.setEnabled(True)

    def get_settings(self):
        port = self.com_port_combo.currentData()
        if not port:
            port = self.com_port_combo.currentText()
        try:
            baudrate = int(self.baud_rate_combo.currentText())
        except ValueError:
            baudrate = 921600
        return {"port": port, "baudrate": baudrate}