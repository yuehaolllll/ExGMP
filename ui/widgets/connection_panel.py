from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QRadioButton, QPushButton, QHBoxLayout, QButtonGroup
from PyQt6.QtCore import pyqtSignal
from .serial_settings_panel import SerialSettingsPanel

class ConnectionPanel(QWidget):
    """
    一个包含所有连接选项的自定义面板，用于嵌入到菜单中。
    """
    # 定义信号，用于通知 MainWindow 用户的操作
    connect_clicked = pyqtSignal(str, dict)  # 发射连接类型 ("WiFi" or "Bluetooth")
    disconnect_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(10)

        # --- 连接类型组 ---
        type_group = QGroupBox("Connection Type")
        type_layout = QVBoxLayout()
        self.conn_type_group = QButtonGroup(self)

        self.wifi_radio = QRadioButton("WiFi")
        self.wifi_radio.setChecked(True)  # 默认选中 WiFi
        self.bt_radio = QRadioButton("Bluetooth")
        self.serial_radio = QRadioButton("Serial (UART)")

        # 将按钮添加到 QButtonGroup，这样我们就可以轻松获取选中的那个
        self.conn_type_group.addButton(self.wifi_radio)
        self.conn_type_group.addButton(self.bt_radio)
        self.conn_type_group.addButton(self.serial_radio)

        type_layout.addWidget(self.wifi_radio)
        type_layout.addWidget(self.bt_radio)
        type_layout.addWidget(self.serial_radio)
        type_group.setLayout(type_layout)

        self.serial_settings = SerialSettingsPanel()
        self.serial_settings.setVisible(False)  # 初始时隐藏

        # --- 操作按钮 ---
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.disconnect_btn)

        # --- 连接内部信号 ---
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self.disconnect_clicked.emit)

        # 将所有部分添加到主布局
        main_layout.addWidget(type_group)
        main_layout.addWidget(self.serial_settings)
        main_layout.addLayout(button_layout)

        # 1. 临时显示所有控件，以便布局系统计算出完全展开后的大小
        self.serial_settings.setVisible(True)
        # 2. 获取这个“最大尺寸”
        expanded_size = self.sizeHint()
        # 3. 将这个尺寸设置为本控件的“最小尺寸”
        self.setMinimumSize(expanded_size)
        # 4. 现在，将串口设置恢复为初始的隐藏状态
        self.serial_settings.setVisible(False)

        self.serial_radio.toggled.connect(self.serial_settings.setVisible)

        # 初始化按钮状态
        self.update_status(False)

    def _on_connect(self):
        """当连接按钮被点击时，获取当前选中的类型和参数并发出信号。"""
        checked_button = self.conn_type_group.checkedButton()
        if not checked_button:
            return

        conn_type = checked_button.text()
        params = {}

        if conn_type == "Serial (UART)":
            params = self.serial_settings.get_settings()
            if not params.get("port") or params.get("port") == "No ports found":
                print("Error: No valid COM port selected.")
                return

        # 发射信号，附带类型和参数字典
        self.connect_clicked.emit(conn_type, params)

    def update_status(self, is_connected):
        """
        一个公开方法，由 MainWindow 调用，用于根据连接状态更新面板UI。
        """
        self.connect_btn.setEnabled(not is_connected)
        self.disconnect_btn.setEnabled(is_connected)

        # 当已连接时，禁用类型选择，防止中途更改
        self.wifi_radio.setEnabled(not is_connected)
        self.bt_radio.setEnabled(not is_connected)
        self.serial_radio.setEnabled(not is_connected)