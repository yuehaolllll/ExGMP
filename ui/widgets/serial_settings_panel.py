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

        com_port_layout = QHBoxLayout()
        com_port_layout.addWidget(self.com_port_combo)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_com_ports)
        com_port_layout.addWidget(refresh_button)

        # --- 波特率选择 ---
        self.baud_rate_combo = QComboBox()
        common_baud_rates = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        self.baud_rate_combo.addItems(common_baud_rates)
        # 根据您的硬件代码，将 921600 设为默认值
        self.baud_rate_combo.setCurrentText("921600")

        # 将控件添加到表单布局
        layout.addRow(QLabel("COM Port:"), com_port_layout)
        layout.addRow(QLabel("Baud Rate:"), self.baud_rate_combo)

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
            for port in sorted(ports):
                self.com_port_combo.addItem(port.device, port.device)  # (text, data)
            self.com_port_combo.setEnabled(True)

    def get_settings(self):
        """返回当前选中的配置"""
        port = self.com_port_combo.currentData()
        baudrate = int(self.baud_rate_combo.currentText())
        return {"port": port, "baudrate": baudrate}