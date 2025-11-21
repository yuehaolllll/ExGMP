# File: ui/widgets/serial_settings_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                             QPushButton, QLabel, QFormLayout)
import serial.tools.list_ports


class SerialSettingsPanel(QWidget):
    """
    一个用于配置串口参数的UI面板。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QFormLayout(self)
        layout.setContentsMargins(5, 10, 5, 5)
        layout.setSpacing(10)

        # --- COM 端口选择 ---
        self.com_port_combo = QComboBox()
        # 让下拉框稍微宽一点，防止长描述被截断
        self.com_port_combo.setMinimumWidth(150)

        com_port_layout = QHBoxLayout()
        com_port_layout.addWidget(self.com_port_combo, stretch=1)

        refresh_button = QPushButton("⟳")  # 使用符号更简洁
        refresh_button.setFixedWidth(30)
        refresh_button.setToolTip("Refresh Ports")
        refresh_button.clicked.connect(self.refresh_com_ports)
        com_port_layout.addWidget(refresh_button)

        # --- 波特率选择 ---
        self.baud_rate_combo = QComboBox()
        # 补充了 1M 和 2M 的波特率，现代 MCU (如 ESP32) 常用于高速传输
        common_baud_rates = ["9600", "19200", "38400", "57600", "115200",
                             "230400", "460800", "921600", "1000000", "2000000"]
        self.baud_rate_combo.addItems(common_baud_rates)
        self.baud_rate_combo.setEditable(True)  # 允许手动输入非标准波特率
        self.baud_rate_combo.setCurrentText("921600")

        # 将控件添加到表单布局
        layout.addRow(QLabel("Port:"), com_port_layout)
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