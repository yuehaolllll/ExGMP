# File: ui/widgets/refined_ble_scan_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QListWidgetItem, QLabel, QStackedWidget,
                             QWidget, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, QThread, QObject, Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QMovie
import asyncio
import os
import sys

# 确保安装了 bleak
try:
    from bleak import BleakScanner
except ImportError:
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
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            for device in devices:
                if device.name and device.name != "Unknown":
                    self.device_found.emit(device.name, device.address)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()


class RefinedBleScanDialog(QDialog):
    device_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan for BLE Devices")
        self.setFixedSize(500, 420)

        # --- 样式表美化 (多彩按钮版) ---
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; }

            /* 列表样式 */
            QListWidget {
                background-color: #F8F9FA;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                outline: none;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-radius: 6px;
                color: #333;
                margin-bottom: 6px;
                background-color: #FFFFFF;
                border: 1px solid #EEE;
            }
            QListWidget::item:hover {
                background-color: #F1F3F4;
                border-color: #CCC;
            }
            QListWidget::item:selected {
                background-color: #E8F0FE;
                color: #1967D2;
                border: 1px solid #1967D2;
                font-weight: 600;
            }

            /* 标签 */
            QLabel { color: #5F6368; font-size: 13px; }
            QLabel#loadingText { 
                color: #1A73E8; font-weight: 600; font-size: 15px; margin-top: 15px; 
            }

            /* 按钮通用设置 */
            QPushButton {
                border-radius: 4px; 
                padding: 8px 18px; 
                font-size: 13px; 
                font-weight: bold;
                border: none;
                color: white; /* 默认文字白色 */
            }

            /* 1. Connect 按钮 (蓝色 - 主要操作) */
            QPushButton#btnConnect {
                background-color: #1A73E8; 
            }
            QPushButton#btnConnect:hover { background-color: #1557B0; }
            QPushButton#btnConnect:pressed { background-color: #0D47A1; }
            QPushButton#btnConnect:disabled { 
                background-color: #F1F3F4; color: #BDC1C6; border: 1px solid #E0E0E0;
            }

            /* 2. Rescan 按钮 (绿色 - 刷新操作) */
            QPushButton#btnRescan {
                background-color: #28A745; /* Material Green */
            }
            QPushButton#btnRescan:hover { background-color: #218838; }
            QPushButton#btnRescan:pressed { background-color: #1E7E34; }
            QPushButton#btnRescan:disabled {
                background-color: #E8F5E9; color: #A5D6A7;
            }

            /* 3. Cancel 按钮 (红色 - 退出操作) */
            QPushButton#btnCancel {
                background-color: #DC3545; /* Material Red */
            }
            QPushButton#btnCancel:hover { background-color: #C82333; }
            QPushButton#btnCancel:pressed { background-color: #BD2130; }
        """)

        # 图标加载
        self.bt_icon = QIcon(resource_path("icons/bluetooth.svg"))

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # 堆叠页面
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # --- Page 1: Loading ---
        spinner_page = QWidget()
        spinner_layout = QVBoxLayout(spinner_page)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spinner_movie = QMovie(resource_path("icons/spinner.gif"))
        self.spinner_movie.setScaledSize(QSize(50, 50))

        self.spinner_label = QLabel()
        self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        loading_text = QLabel("Scanning nearby devices...")
        loading_text.setObjectName("loadingText")
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner_layout.addStretch()
        spinner_layout.addWidget(self.spinner_label)
        spinner_layout.addWidget(loading_text)
        spinner_layout.addStretch()

        self.stacked_widget.addWidget(spinner_page)

        # --- Page 2: List Result ---
        self.device_list = QListWidget()
        self.device_list.setIconSize(QSize(24, 24))
        self.device_list.itemDoubleClicked.connect(self._on_device_selected)
        self.device_list.currentItemChanged.connect(self._update_connect_button_state)
        self.stacked_widget.addWidget(self.device_list)

        # --- 底部状态栏 ---
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Initializing...")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # --- 底部按钮区 ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # 左侧：Rescan (绿色)
        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.setObjectName("btnRescan")
        self.rescan_button.setCursor(Qt.CursorShape.PointingHandCursor)

        button_layout.addWidget(self.rescan_button)

        button_layout.addStretch()  # 弹簧撑开左右

        # 右侧：Cancel (红色) + Connect (蓝色)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("btnCancel")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("btnConnect")
        self.connect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_button.setDefault(True)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.connect_button)

        main_layout.addLayout(button_layout)

        # 逻辑连接
        self.rescan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.reject)
        self.connect_button.clicked.connect(self._on_device_selected)

        self.scanner_thread = None
        self._update_connect_button_state()

    def start_scan(self):
        self.device_list.clear()
        self.status_label.setText("Searching for devices...")

        self.stacked_widget.setCurrentIndex(0)
        self.spinner_movie.start()

        self.rescan_button.setEnabled(False)
        self.connect_button.setEnabled(False)

        if self.scanner_thread is not None:
            try:
                if self.scanner_thread.isRunning():
                    self.scanner_thread.quit()
                    self.scanner_thread.wait()
            except RuntimeError:
                pass
            self.scanner_thread = None

        self.scanner_thread = QThread()
        self.scanner_worker = BleScannerWorker()
        self.scanner_worker.moveToThread(self.scanner_thread)

        self.scanner_worker.device_found.connect(self._add_device_to_list)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_worker.error_occurred.connect(self._on_scan_error)

        self.scanner_thread.started.connect(self.scanner_worker.run)
        self.scanner_worker.finished.connect(self.scanner_thread.quit)
        self.scanner_worker.finished.connect(self.scanner_worker.deleteLater)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)

        self.scanner_thread.start()

    def _add_device_to_list(self, name, address):
        items = self.device_list.findItems(name, Qt.MatchFlag.MatchStartsWith)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole)[1] == address:
                return

        item = QListWidgetItem(self.bt_icon, f"{name}  [{address}]")
        item.setData(Qt.ItemDataRole.UserRole, (name, address))
        self.device_list.addItem(item)

    def _on_scan_finished(self):
        self.spinner_movie.stop()
        self.stacked_widget.setCurrentIndex(1)
        self.rescan_button.setEnabled(True)

        count = self.device_list.count()
        if count == 0:
            self.status_label.setText("No devices found.")
            empty_item = QListWidgetItem("No devices found. Click Rescan.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.device_list.addItem(empty_item)
        else:
            self.status_label.setText(f"Found {count} device(s).")

    def _on_scan_error(self, error_msg):
        self.status_label.setStyleSheet("color: #D32F2F;")
        self.status_label.setText(f"Error: {error_msg}")

    def _update_connect_button_state(self):
        current = self.device_list.currentItem()
        self.connect_button.setEnabled(current is not None and current.flags() & Qt.ItemFlag.ItemIsEnabled)

    def _on_device_selected(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            data = selected_item.data(Qt.ItemDataRole.UserRole)
            if data:
                name, address = data
                print(f"Dialog: User selected {name} ({address})")
                self.device_selected.emit(name, address)
                self.accept()

    def exec_and_scan(self):
        QTimer.singleShot(100, self.start_scan)
        return self.exec()