# In ui/widgets/tools_panel.py (FINAL AND CORRECTED VERSION)

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

# This style remains the same, but will now work correctly.
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
    """
    一个包含所有辅助采集工具的自定义面板，用于嵌入到菜单中。
    """
    eog_acquisition_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use a simpler layout without the QGroupBox
        main_layout = QVBoxLayout(self)
        # Use tighter margins to make it feel more like a part of the menu
        main_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.setSpacing(0)

        self.eog_button = QPushButton("EOG Acquisition Guide")

        # Apply the style directly to the button
        self.eog_button.setStyleSheet(MENU_BUTTON_STYLE)

        # --- THIS IS THE CRITICAL FIX ---
        # Force the button to be flat, giving QSS full control over its appearance
        self.eog_button.setFlat(True)

        self.eog_button.clicked.connect(self.eog_acquisition_triggered.emit)
        main_layout.addWidget(self.eog_button)

        # Future buttons can be added here using the same technique:
        # self.emg_button = QPushButton("EMG Acquisition Guide")
        # self.emg_button.setStyleSheet(MENU_BUTTON_STYLE)
        # self.emg_button.setFlat(True)
        # main_layout.addWidget(self.emg_button)

        self.update_status(False)

    def update_status(self, is_enabled):
        """
        一个公开方法，由 MainWindow 调用，用于根据连接或采集状态更新面板UI。
        """
        self.eog_button.setEnabled(is_enabled)