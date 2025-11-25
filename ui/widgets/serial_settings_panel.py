# File: ui/widgets/serial_settings_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                             QPushButton, QLabel, QFormLayout, QStyle)
import serial.tools.list_ports
from PyQt6.QtCore import Qt

class SerialSettingsPanel(QWidget):
    """
    一个用于配置串口参数的UI面板。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #F0F4F8; border-radius: 6px;")
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)  # 标签左对齐

        # --- COM 端口 ---
        self.com_port_combo = QComboBox()
        self.com_port_combo.setMinimumHeight(30)  # 增加高度

        com_layout = QHBoxLayout()
        com_layout.setSpacing(8)
        com_layout.addWidget(self.com_port_combo, stretch=1)

        self.refresh_btn = QPushButton()
        # 使用 Qt 内置的标准“刷新/重载”图标
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self.refresh_btn.setObjectName("btnNormal")
        self.refresh_btn.setFixedSize(32, 32)  # 稍微大一点，正方形
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh Serial Ports")
        self.refresh_btn.clicked.connect(self.refresh_com_ports)

        com_layout.addWidget(self.refresh_btn)

        # --- 波特率选择 ---
        self.baud_rate_combo = QComboBox()
        self.baud_rate_combo.setMinimumHeight(32)
        # 补充了 1M 和 2M 的波特率，现代 MCU (如 ESP32) 常用于高速传输
        common_baud_rates = ["9600", "19200", "38400", "57600", "115200",
                             "230400", "460800", "921600", "1000000", "2000000"]
        self.baud_rate_combo.addItems(common_baud_rates)
        self.baud_rate_combo.setEditable(True)  # 允许手动输入非标准波特率
        self.baud_rate_combo.setCurrentText("921600")

        # 将控件添加到表单布局
        layout.addRow(QLabel("Port:"), com_layout)
        layout.addRow(QLabel("Baud:"), self.baud_rate_combo)

        # 初始时刷新一次COM口列表
        self.refresh_com_ports()

    def refresh_com_ports(self):
        """刷新可用的COM端口列表"""
        self.com_port_combo.clear()
        ports = serial.tools.list_ports.comports()

        if not ports:
            self.com_port_combo.addItem("No ports found")
            self.com_port_combo.setEnabled(False)
        else:
            # --- 优化：按设备名排序 (COM1, COM2, ...) ---
            # 使用 lambda 键值排序，防止直接排序对象报错
            sorted_ports = sorted(ports, key=lambda p: p.device)

            for port in sorted_ports:
                # 显示格式: "COM3 (USB Serial Device)"
                display_text = f"{port.device}"
                if port.description and port.description != "n/a":
                    display_text += f" ({port.description})"

                self.com_port_combo.addItem(display_text, port.device)  # (显示文本, 实际数据)

            self.com_port_combo.setEnabled(True)

    def get_settings(self):
        """返回当前选中的配置"""
        port = self.com_port_combo.currentData()

        # 如果没有 Data (例如 "No ports found")，尝试取 Text
        if not port:
            port = self.com_port_combo.currentText()

        try:
            baudrate = int(self.baud_rate_combo.currentText())
        except ValueError:
            baudrate = 921600  # 默认回退值

        return {"port": port, "baudrate": baudrate}