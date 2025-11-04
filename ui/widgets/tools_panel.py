# In ui/widgets/tools_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGroupBox, QGridLayout, QLabel, QCheckBox
from PyQt6.QtCore import pyqtSignal

MENU_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        border: none; /* Remove border completely */
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
    eog_acquisition_triggered = pyqtSignal()
    # 信号1: 请求开始 ICA 校准，并告知需要的数据时长
    ica_calibration_triggered = pyqtSignal(int)
    # 信号2: 切换 ICA 清理功能的状态 (启用/禁用)
    ica_toggle_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use a simpler layout without the QGroupBox
        main_layout = QVBoxLayout(self)
        # Use tighter margins to make it feel more like a part of the menu
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        self.eog_button = QPushButton("EOG Acquisition Guide")

        # Apply the style directly to the button
        self.eog_button.setStyleSheet(MENU_BUTTON_STYLE)

        # --- THIS IS THE CRITICAL FIX ---
        # Force the button to be flat, giving QSS full control over its appearance
        self.eog_button.setFlat(True)

        self.eog_button.clicked.connect(self.eog_acquisition_triggered.emit)
        main_layout.addWidget(self.eog_button)

        # --- ICA 伪迹去除工具组 ---
        ica_group = QGroupBox("ICA Artifact Removal")
        ica_group.setStyleSheet("font-weight: normal;")  # 使组内字体正常
        ica_layout = QGridLayout()
        ica_layout.setSpacing(8)

        # 1. 开始校准按钮
        self.calibrate_ica_btn = QPushButton("Start Calibration")
        self.calibrate_ica_btn.setToolTip("Collect 30s of data to train the ICA model.")
        self.calibrate_ica_btn.clicked.connect(self._on_start_calibration)

        # 2. 状态标签
        self.ica_status_lbl = QLabel("Status: Not Calibrated")

        # 3. 启用/禁用复选框
        self.enable_ica_checkbox = QCheckBox("Enable ICA Cleaning")
        self.enable_ica_checkbox.toggled.connect(self.ica_toggle_changed.emit)

        ica_layout.addWidget(self.calibrate_ica_btn, 0, 0, 1, 2)
        ica_layout.addWidget(self.ica_status_lbl, 1, 0, 1, 2)
        ica_layout.addWidget(self.enable_ica_checkbox, 2, 0, 1, 2)

        ica_group.setLayout(ica_layout)
        main_layout.addWidget(ica_group)

        self.update_status(False)

    def _on_start_calibration(self):
        # 这里可以设置校准时长，暂时硬编码为30秒
        calibration_duration_seconds = 30
        self.ica_calibration_triggered.emit(calibration_duration_seconds)

        # 更新UI，防止重复点击
        self.calibrate_ica_btn.setEnabled(False)
        self.ica_status_lbl.setText("Status: Calibrating...")

    def set_calibration_finished(self):
        """一个公开方法，当ICA模型训练完成后由外部调用"""
        self.ica_status_lbl.setText("Status: Ready to Enable")
        self.calibrate_ica_btn.setEnabled(True)  # 允许重新校准
        self.enable_ica_checkbox.setEnabled(True)  # 现在可以启用了

    def update_status(self, is_connected):
        """根据连接状态更新面板UI"""
        self.eog_button.setEnabled(is_connected)
        self.calibrate_ica_btn.setEnabled(is_connected)

        # 只有在连接断开时，才彻底重置ICA状态
        if not is_connected:
            self.ica_status_lbl.setText("Status: Not Calibrated")
            self.enable_ica_checkbox.setEnabled(False)
            self.enable_ica_checkbox.setChecked(False)