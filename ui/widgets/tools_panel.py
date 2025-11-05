# In ui/widgets/tools_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QMenu
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction

# 按钮的样式保持不变，它将被用于我们的主按钮
MENU_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        border-radius: 1px;
        padding: 5px 25px 5px 20px; 
        text-align: left;
        font-weight: normal;
        color: #212121;
    }
    QPushButton:hover {
        background-color: #007BFF;
        color: #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #0056b3;
    }
    QPushButton:disabled {
        background: transparent;
        color: #BDBDBD;
    }
"""


class ToolsPanel(QWidget):
    # 对外暴露的信号完全不变，所以 MainWindow 不需要任何修改
    eog_acquisition_triggered = pyqtSignal()
    ica_calibration_triggered = pyqtSignal(int)
    ica_toggle_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)

        # 1. EOG 指南按钮
        self.eog_button = QPushButton("EOG Acquisition Guide")
        self.eog_button.setStyleSheet(MENU_BUTTON_STYLE)
        self.eog_button.setFlat(True)
        self.eog_button.clicked.connect(self.eog_acquisition_triggered.emit)
        main_layout.addWidget(self.eog_button)

        # --- 3. 创建带子菜单的ICA功能按钮 ---
        # a. 创建主按钮
        self.ica_menu_button = QPushButton("ICA Artifact Removal")
        self.ica_menu_button.setStyleSheet(MENU_BUTTON_STYLE)
        self.ica_menu_button.setFlat(True)

        # b. 创建子菜单
        self.ica_submenu = QMenu(self)

        # c. 创建子菜单中的 "Action"
        self.calibrate_action = QAction("Calibrate ICA Model", self)
        self.calibrate_action.triggered.connect(self._on_start_calibration)

        self.enable_action = QAction("Enable ICA Cleaning", self)
        self.enable_action.setCheckable(True)  # 设置为可勾选
        self.enable_action.toggled.connect(self.ica_toggle_changed.emit)

        # d. 将 Action 添加到子菜单
        self.ica_submenu.addAction(self.calibrate_action)
        self.ica_submenu.addAction(self.enable_action)

        # e. 将子菜单关联到主按钮
        self.ica_menu_button.setMenu(self.ica_submenu)

        # f. 将主按钮添加到布局
        main_layout.addWidget(self.ica_menu_button)

        # 初始化UI状态
        self.update_status(False)

    def _on_start_calibration(self):
        calibration_duration_seconds = 30
        self.ica_calibration_triggered.emit(calibration_duration_seconds)

        # 更新UI，进入“正在校准”状态
        self.calibrate_action.setText("Calibrating...")
        self.calibrate_action.setEnabled(False)
        self.eog_button.setEnabled(False)

    def set_calibration_finished(self):
        """当ICA模型训练完成后由外部调用"""
        self.calibrate_action.setText("Re-calibrate ICA Model")
        self.calibrate_action.setEnabled(True)
        self.enable_action.setEnabled(True)  # 启用 "Enable" 选项
        self.eog_button.setEnabled(True)

    def reset_calibration_ui(self):
        """重置ICA UI到默认状态 (用于取消或失败)"""
        self.calibrate_action.setText("Calibrate ICA Model")
        self.eog_button.setEnabled(True)

    def update_status(self, is_connected):
        """根据连接状态更新整个面板的UI"""
        self.eog_button.setEnabled(is_connected)
        self.ica_menu_button.setEnabled(is_connected)  # 主按钮只根据连接状态变化

        if not is_connected:
            # 断开连接时，彻底重置所有子菜单项的状态
            self.calibrate_action.setText("Calibrate ICA Model")
            self.calibrate_action.setEnabled(False)
            self.enable_action.setEnabled(False)
            self.enable_action.setChecked(False)
        else:
            # 刚连接时，启用校准项，但禁用切换项
            self.calibrate_action.setEnabled(True)
            # 只有当模型校准完成后，enable_action才应该是可用的
            if self.calibrate_action.text() == "Calibrate ICA Model":
                self.enable_action.setEnabled(False)

    def set_training_state(self):
        """一个由外部调用的新方法，用于将UI更新为“正在训练”状态"""
        self.calibrate_action.setText("Training model...")
        self.calibrate_action.setEnabled(False)  # 保持禁用状态