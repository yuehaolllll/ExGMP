from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QProgressDialog, QListWidgetItem
from PyQt6.QtCore import pyqtSignal, QThread, QObject, Qt
import asyncio
from bleak import BleakScanner


class BleScannerWorker(QObject):
    """在一个单独的线程中运行bleak扫描，以避免阻塞UI"""
    device_found = pyqtSignal(str, str)  # name, address
    finished = pyqtSignal()

    def run(self):
        asyncio.run(self.scan())

    async def scan(self):
        print("Starting BLE scan...")
        devices = await BleakScanner.discover()
        for device in devices:
            if device.name:  # 只显示有名字的设备
                self.device_found.emit(device.name, device.address)
        self.finished.emit()
        print("BLE scan finished.")


class BleScanDialog(QDialog):
    device_selected = pyqtSignal(str, str)  # name, address

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan for BLE Devices")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)

        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._on_device_selected)
        layout.addWidget(self.device_list)

        self.scan_button = QPushButton("Rescan")
        self.scan_button.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_button)

        self.select_button = QPushButton("Select Device")
        self.select_button.clicked.connect(self._on_device_selected)
        layout.addWidget(self.select_button)

        self.scanner_thread = None

    def start_scan(self):
        self.device_list.clear()
        self.scan_button.setEnabled(False)
        self.scan_button.setText("Scanning...")

        # 使用QThread来运行扫描
        self.scanner_thread = QThread()
        self.scanner_worker = BleScannerWorker()
        self.scanner_worker.moveToThread(self.scanner_thread)

        self.scanner_worker.device_found.connect(self._add_device_to_list)
        self.scanner_thread.started.connect(self.scanner_worker.run)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_thread.start()

    def _add_device_to_list(self, name, address):
        item_text = f"{name} ({address})"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, (name, address))  # 将数据附加到item上
        self.device_list.addItem(item)

    def _on_scan_finished(self):
        self.scan_button.setEnabled(True)
        self.scan_button.setText("Rescan")
        self.scanner_thread.quit()
        self.scanner_thread.wait()

    def _on_device_selected(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            name, address = selected_item.data(Qt.ItemDataRole.UserRole)
            self.device_selected.emit(name, address)
            self.accept()  # 关闭对话框并返回 QDialog.DialogCode.Accepted

    def exec_and_scan(self):
        # 这是一个辅助函数，用于打开对话框时立即开始扫描
        self.start_scan()
        return self.exec()