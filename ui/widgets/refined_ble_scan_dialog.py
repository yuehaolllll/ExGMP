# File: ui/widgets/refined_ble_scan_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QListWidgetItem, QLabel, QStackedWidget,
                             QWidget, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, QThread, QObject, Qt, QSize
from PyQt6.QtGui import QIcon, QMovie
import asyncio
import os
import sys

# 确保安装了 bleak
try:
    from bleak import BleakScanner
except ImportError:
    print("Error: 'bleak' library not found. Please install it via 'pip install bleak'")
    BleakScanner = None


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class BleScannerWorker(QObject):
    """后台扫描工作者"""
    device_found = pyqtSignal(str, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        if BleakScanner is None:
            self.error_occurred.emit("Bleak library not installed.")
            self.finished.emit()
            return
        try:
            asyncio.run(self.scan())
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.finished.emit()

    async def scan(self):
        print("Worker: Starting BLE scan...")
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            for device in devices:
                if device.name and device.name != "Unknown":
                    self.device_found.emit(device.name, device.address)
        except Exception as e:
            print(f"Worker Error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            print("Worker: Scan finished.")
            self.finished.emit()


class RefinedBleScanDialog(QDialog):
    device_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan for BLE Devices")
        self.setFixedSize(450, 350)

        self.setStyleSheet("""
            QListWidget { border: 1px solid #CCC; border-radius: 4px; padding: 5px; font-size: 14px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #EEE; }
            QListWidget::item:selected { background-color: #E3F2FD; color: #333; border: 1px solid #2196F3; border-radius: 4px; }
            QLabel { font-size: 13px; color: #555; }
            QPushButton { padding: 6px 12px; border-radius: 4px; }
        """)

        self.bt_icon = QIcon(resource_path("icons/bluetooth.svg"))
        self.spinner_movie = QMovie(resource_path("icons/spinner.gif"))
        self.spinner_movie.setScaledSize(QSize(64, 64))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Page 1: Spinner
        spinner_page = QWidget()
        spinner_layout = QVBoxLayout(spinner_page)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label = QLabel()
        self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text = QLabel("Scanning nearby devices...")
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        spinner_layout.addWidget(self.spinner_label)
        spinner_layout.addWidget(loading_text)
        self.stacked_widget.addWidget(spinner_page)

        # Page 2: List
        self.device_list = QListWidget()
        self.device_list.setIconSize(QSize(24, 24))
        self.device_list.itemDoubleClicked.connect(self._on_device_selected)
        self.device_list.currentItemChanged.connect(self._update_connect_button_state)
        self.stacked_widget.addWidget(self.device_list)

        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        self.rescan_button = QPushButton("Rescan")
        self.cancel_button = QPushButton("Cancel")
        self.connect_button = QPushButton("Connect")
        self.connect_button.setDefault(True)

        button_layout.addWidget(self.rescan_button)
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.connect_button)
        main_layout.addLayout(button_layout)

        self.rescan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.reject)
        self.connect_button.clicked.connect(self._on_device_selected)

        self.scanner_thread = None
        self._update_connect_button_state()

    def start_scan(self):
        """启动或重新启动扫描"""
        self.device_list.clear()
        self.status_label.setText("Scanning...")

        self.stacked_widget.setCurrentIndex(0)
        self.spinner_movie.start()

        self.rescan_button.setEnabled(False)
        self.connect_button.setEnabled(False)

        # --- 核心修复：安全地清理旧线程 ---
        if self.scanner_thread is not None:
            try:
                # 尝试访问 isRunning，如果对象已被 C++ 删除，这里会抛出 RuntimeError
                if self.scanner_thread.isRunning():
                    self.scanner_thread.quit()
                    self.scanner_thread.wait()
            except RuntimeError:
                # 对象已经被删除了，无需操作，直接 pass
                pass
            # 无论如何，将引用置为 None，准备创建新的
            self.scanner_thread = None

        # --- 创建新线程 ---
        self.scanner_thread = QThread()
        self.scanner_worker = BleScannerWorker()
        self.scanner_worker.moveToThread(self.scanner_thread)

        self.scanner_worker.device_found.connect(self._add_device_to_list)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_worker.error_occurred.connect(self._on_scan_error)

        self.scanner_thread.started.connect(self.scanner_worker.run)

        # 清理逻辑：保留 deleteLater，但依靠上面的 try-except 保护下次调用
        self.scanner_worker.finished.connect(self.scanner_thread.quit)
        self.scanner_worker.finished.connect(self.scanner_worker.deleteLater)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)

        self.scanner_thread.start()

    def _add_device_to_list(self, name, address):
        items = self.device_list.findItems(name, Qt.MatchFlag.MatchStartsWith)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole)[1] == address:
                return

        item_text = f"{name}  [{address}]"
        item = QListWidgetItem(self.bt_icon, item_text)
        item.setData(Qt.ItemDataRole.UserRole, (name, address))
        self.device_list.addItem(item)

    def _on_scan_finished(self):
        self.spinner_movie.stop()
        self.stacked_widget.setCurrentIndex(1)
        self.rescan_button.setEnabled(True)

        count = self.device_list.count()
        if count == 0:
            self.status_label.setText("No devices found.")
        else:
            self.status_label.setText(f"Found {count} device(s). Ready to connect.")
            if self.device_list.count() > 0:
                self.device_list.setCurrentRow(0)

    def _on_scan_error(self, error_msg):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(f"Error: {error_msg}")

    def _update_connect_button_state(self):
        self.connect_button.setEnabled(self.device_list.currentItem() is not None)

    def _on_device_selected(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            data = selected_item.data(Qt.ItemDataRole.UserRole)
            name, address = data
            print(f"Dialog: User selected {name} ({address})")
            self.device_selected.emit(name, address)
            self.accept()

    def exec_and_scan(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.start_scan)
        return self.exec()