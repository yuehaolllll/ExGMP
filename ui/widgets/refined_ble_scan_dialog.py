from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QListWidgetItem, QLabel, QStackedWidget,
                             QWidget, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, QThread, QObject, Qt
from PyQt6.QtGui import QIcon, QMovie
import asyncio
from bleak import BleakScanner


# --- 复用 BleScannerWorker ---
# （这段代码与旧的 ble_scan_dialog.py 中的完全相同）
class BleScannerWorker(QObject):
    device_found = pyqtSignal(str, str)
    finished = pyqtSignal()

    def run(self):
        asyncio.run(self.scan())

    async def scan(self):
        print("Starting BLE scan...")
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            for device in devices:
                if device.name:
                    self.device_found.emit(device.name, device.address)
        except Exception as e:
            print(f"An error occurred during BLE scan: {e}")
        finally:
            self.finished.emit()
            print("BLE scan finished.")


# --- 全新的、精致的对话框 ---
class RefinedBleScanDialog(QDialog):
    device_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan for BLE Devices")
        self.setFixedSize(450, 350)

        # --- 图标和动画 ---
        self.bt_icon = QIcon("icons/bluetooth.svg")
        self.spinner_movie = QMovie("icons/spinner.gif")

        # --- 主布局 ---
        main_layout = QVBoxLayout(self)

        # --- 1. 堆叠窗口（用于切换“扫描中”和“列表”） ---
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # 页面1: 扫描动画
        spinner_page = QWidget()
        spinner_layout = QVBoxLayout(spinner_page)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label = QLabel()
        self.spinner_label.setMovie(self.spinner_movie)
        spinner_layout.addWidget(self.spinner_label)
        self.stacked_widget.addWidget(spinner_page)

        # 页面2: 设备列表
        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._on_device_selected)
        self.device_list.currentItemChanged.connect(self._update_connect_button_state)
        self.stacked_widget.addWidget(self.device_list)

        # --- 2. 状态标签 ---
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # --- 3. 底部按钮 ---
        button_layout = QHBoxLayout()
        self.rescan_button = QPushButton("Rescan")
        self.cancel_button = QPushButton("Cancel")
        self.connect_button = QPushButton("Connect")

        button_layout.addWidget(self.rescan_button)
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.connect_button)
        main_layout.addLayout(button_layout)

        # --- 信号连接 ---
        self.rescan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.reject)  # reject() 关闭对话框并返回 Rejected
        self.connect_button.clicked.connect(self._on_device_selected)

        self.scanner_thread = None
        self._update_connect_button_state()  # 初始禁用 Connect 按钮

    def start_scan(self):
        self.device_list.clear()
        self.status_label.setText("Scanning for devices...")
        self.stacked_widget.setCurrentIndex(0)  # 切换到扫描动画页面
        self.spinner_movie.start()

        self.rescan_button.setEnabled(False)
        self._update_connect_button_state()

        # 使用 QThread 运行扫描 (逻辑不变)
        self.scanner_thread = QThread()
        self.scanner_worker = BleScannerWorker()
        self.scanner_worker.moveToThread(self.scanner_thread)
        self.scanner_worker.device_found.connect(self._add_device_to_list)
        self.scanner_thread.started.connect(self.scanner_worker.run)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_thread.start()

    def _add_device_to_list(self, name, address):
        item_text = f"{name}\n{address}"  # 将地址放在第二行
        item = QListWidgetItem(self.bt_icon, item_text)
        item.setData(Qt.ItemDataRole.UserRole, (name, address))
        self.device_list.addItem(item)

    def _on_scan_finished(self):
        self.spinner_movie.stop()
        self.stacked_widget.setCurrentIndex(1)  # 切换到设备列表页面
        self.rescan_button.setEnabled(True)

        if self.device_list.count() == 0:
            self.status_label.setText("No devices found. Ensure device is discoverable.")
        else:
            self.status_label.setText(f"Scan complete. Found {self.device_list.count()} device(s).")
            self.device_list.setCurrentRow(0)  # 默认选中第一项

        if self.scanner_thread:
            self.scanner_thread.quit()
            self.scanner_thread.wait()

    def _update_connect_button_state(self):
        # 只有当有设备被选中时，Connect 按钮才可用
        self.connect_button.setEnabled(self.device_list.currentItem() is not None)

    def _on_device_selected(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            name, address = selected_item.data(Qt.ItemDataRole.UserRole)
            self.device_selected.emit(name, address)
            self.accept()  # 关闭对话框并返回 Accepted

    def exec_and_scan(self):
        self.start_scan()
        return self.exec()