from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QRadioButton, QPushButton, QHBoxLayout, QButtonGroup
from PyQt6.QtCore import pyqtSignal


class ConnectionPanel(QWidget):
    """
    一个包含所有连接选项的自定义面板，用于嵌入到菜单中。
    """
    # 定义信号，用于通知 MainWindow 用户的操作
    connect_clicked = pyqtSignal(str)  # 发射连接类型 ("WiFi" or "Bluetooth")
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

        # 将按钮添加到 QButtonGroup，这样我们就可以轻松获取选中的那个
        self.conn_type_group.addButton(self.wifi_radio)
        self.conn_type_group.addButton(self.bt_radio)

        type_layout.addWidget(self.wifi_radio)
        type_layout.addWidget(self.bt_radio)
        type_group.setLayout(type_layout)

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
        main_layout.addLayout(button_layout)

        # 初始化按钮状态
        self.update_status(False)

    def _on_connect(self):
        """当连接按钮被点击时，获取当前选中的类型并发出信号。"""
        checked_button = self.conn_type_group.checkedButton()
        if checked_button:
            # 发射被选中按钮的文本 ("WiFi" or "Bluetooth")
            self.connect_clicked.emit(checked_button.text())

    def update_status(self, is_connected):
        """
        一个公开方法，由 MainWindow 调用，用于根据连接状态更新面板UI。
        """
        self.connect_btn.setEnabled(not is_connected)
        self.disconnect_btn.setEnabled(is_connected)

        # 当已连接时，禁用类型选择，防止中途更改
        self.wifi_radio.setEnabled(not is_connected)
        self.bt_radio.setEnabled(not is_connected)