# File: ui/widgets/tools_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMenu
from PyQt6.QtCore import pyqtSignal, Qt  # <--- 必须导入 Qt
from PyQt6.QtGui import QAction

# 样式表
MENU_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        border-radius: 4px;
        padding: 8px 10px; 
        text-align: left;
        font-size: 14px;
        color: #333333;
    }
    QPushButton:hover {
        background-color: #E3F2FD;
        color: #1565C0;
    }
    QPushButton:pressed {
        background-color: #BBDEFB;
    }
    QPushButton:disabled {
        background: transparent;
        color: #BDBDBD;
    }
    /* 下拉箭头样式 */
    QPushButton::menu-indicator {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        right: 10px;
        image: none;
        width: 0px;
    }
"""


class ToolsPanel(QWidget):
    # 信号定义
    eog_acquisition_triggered = pyqtSignal()
    ica_calibration_triggered = pyqtSignal(int)
    ica_toggle_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # --- 1. EOG 指南按钮 ---
        self.eog_button = QPushButton("👁  EOG Acquisition Guide")
        self.eog_button.setStyleSheet(MENU_BUTTON_STYLE)

        # --- 修复点：使用正确的光标枚举值 ---
        self.eog_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.eog_button.clicked.connect(self.eog_acquisition_triggered.emit)
        main_layout.addWidget(self.eog_button)

        # --- 2. ICA 功能按钮 (带子菜单) ---
        self.ica_menu_button = QPushButton("🧠  ICA Artifact Removal  ▼")
        self.ica_menu_button.setStyleSheet(MENU_BUTTON_STYLE)
        self.ica_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)  # 同样应用手型光标

        # 创建子菜单
        self.ica_submenu = QMenu(self)
        self.ica_submenu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
            QMenu::item:disabled {
                color: #BDBDBD;
            }
        """)

        # Action 1: 校准
        self.calibrate_action = QAction("Calibrate ICA Model (30s)", self)
        self.calibrate_action.triggered.connect(self._on_start_calibration)

        # Action 2: 启用/禁用
        self.enable_action = QAction("Enable Real-time Cleaning", self)
        self.enable_action.setCheckable(True)
        self.enable_action.toggled.connect(self.ica_toggle_changed.emit)

        self.ica_submenu.addAction(self.calibrate_action)
        self.ica_submenu.addSeparator()
        self.ica_submenu.addAction(self.enable_action)

        self.ica_menu_button.setMenu(self.ica_submenu)
        main_layout.addWidget(self.ica_menu_button)

        # 添加弹簧
        main_layout.addStretch()

        # 初始化UI状态
        self.update_status(False)

    def _on_start_calibration(self):
        calibration_duration_seconds = 30
        self.ica_calibration_triggered.emit(calibration_duration_seconds)

        # 更新UI
        self.calibrate_action.setText("Calibrating (Please wait)...")
        self.calibrate_action.setEnabled(False)
        self.eog_button.setEnabled(False)

    def set_calibration_finished(self):
        self.calibrate_action.setText("Re-calibrate ICA Model")
        self.calibrate_action.setEnabled(True)
        self.enable_action.setEnabled(True)
        self.enable_action.setChecked(True)
        self.eog_button.setEnabled(True)

    def reset_calibration_ui(self):
        self.calibrate_action.setText("Calibrate ICA Model (30s)")
        self.enable_action.setChecked(False)
        self.enable_action.setEnabled(False)
        self.eog_button.setEnabled(True)

    def set_training_state(self):
        self.calibrate_action.setText("Computing ICA (Busy)...")
        self.calibrate_action.setEnabled(False)

    def update_status(self, is_connected):
        self.eog_button.setEnabled(is_connected)
        self.ica_menu_button.setEnabled(is_connected)

        if not is_connected:
            self.reset_calibration_ui()
            self.calibrate_action.setEnabled(False)
        else:
            self.calibrate_action.setEnabled(True)
            if "Calibrate" in self.calibrate_action.text():
                self.enable_action.setEnabled(False)