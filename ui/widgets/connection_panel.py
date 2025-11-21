# File: ui/widgets/connection_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QRadioButton, QPushButton, QHBoxLayout, QButtonGroup
from PyQt6.QtCore import pyqtSignal
from .serial_settings_panel import SerialSettingsPanel


class ConnectionPanel(QWidget):
    """
    一个包含所有连接选项的自定义面板，用于嵌入到菜单中。
    """
    # 定义信号，用于通知 MainWindow 用户的操作
    connect_clicked = pyqtSignal(str, dict)  # 发射连接类型 ("WiFi" or "Bluetooth") 和参数
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
        self.bt_radio = QRadioButton("Bluetooth")
        self.serial_radio = QRadioButton("Serial (UART)")

        self.wifi_radio.setChecked(True)  # 默认选中 WiFi

        # 将按钮添加到 QButtonGroup
        self.conn_type_group.addButton(self.wifi_radio)
        self.conn_type_group.addButton(self.bt_radio)
        self.conn_type_group.addButton(self.serial_radio)

        type_layout.addWidget(self.wifi_radio)
        type_layout.addWidget(self.bt_radio)
        type_layout.addWidget(self.serial_radio)
        type_group.setLayout(type_layout)

        # --- 串口设置面板 ---
        self.serial_settings = SerialSettingsPanel()

        # --- 操作按钮 ---
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        # 默认样式强调连接
        self.connect_btn.setStyleSheet("font-weight: bold; background-color: #E0E0E0;")
        self.disconnect_btn = QPushButton("Disconnect")

        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.disconnect_btn)

        # --- 组装布局 ---
        main_layout.addWidget(type_group)
        main_layout.addWidget(self.serial_settings)
        main_layout.addLayout(button_layout)

        # --- 逻辑连接 ---
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self.disconnect_clicked.emit)

        # 只有选中 Serial 时才显示设置面板
        self.serial_radio.toggled.connect(self.serial_settings.setVisible)

        # --- 核心优化：防止菜单大小抖动 ---
        # 1. 先让所有控件显示出来
        self.serial_settings.setVisible(True)
        # 2. 强制触发布局计算，确保获取的 sizeHint 是准确的
        self.adjustSize()
        # 3. 获取展开后的大小
        expanded_size = self.sizeHint()
        # 4. 锁定最小尺寸，这样即使隐藏了设置面板，菜单也不会突然变小
        self.setMinimumSize(expanded_size)
        # 5. 恢复初始状态
        self.serial_settings.setVisible(False)

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
            # 进行简单的校验
            port = params.get("port")
            if not port or port == "No ports found":
                # 这里可以通过 MainWindow 弹窗提示，或者简单的在控制台打印
                print("Error: No valid COM port selected.")
                # 可以选择让按钮闪烁一下表示错误（可选）
                return

        # 发射信号，附带类型和参数字典
        self.connect_clicked.emit(conn_type, params)

    def update_status(self, is_connected):
        """
        由 MainWindow 调用，更新面板状态
        """
        self.connect_btn.setEnabled(not is_connected)
        self.disconnect_btn.setEnabled(is_connected)

        # 连接中禁止切换类型
        self.wifi_radio.setEnabled(not is_connected)
        self.bt_radio.setEnabled(not is_connected)
        self.serial_radio.setEnabled(not is_connected)

        # 连接中禁止修改串口设置
        self.serial_settings.setEnabled(not is_connected)