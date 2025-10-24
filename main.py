# In main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

import sys
import os
import resources_rc

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

QSS_STYLE = """
/* Global settings - Clean and Professional Light Theme */
QWidget {
    background-color: #F0F2F5;
    color: #212121;
    font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 10pt;
}

/* GroupBox styling */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #DCDCDC;
    border-radius: 6px;
    margin-top: 1ex;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 2px 8px;
    color: #005A9E;
}

/* Default Button styling */
QPushButton {
    background-color: #E0E0E0;
    border: 1px solid #BDBDBD;
    padding: 6px 12px;
    border-radius: 4px;
    color: #212121;
}
QPushButton:hover {
    background-color: #E8E8E8;
    border: 1px solid #007BFF;
}
QPushButton:pressed {
    background-color: #D0D0D0;
}
QPushButton:disabled {
    background-color: #F5F5F5;
    color: #BDBDBD;
}

/* Input fields styling */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #BDBDBD;
    border-radius: 4px;
    padding: 5px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #007BFF;
}

/* CheckBox styling */
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #BDBDBD;
    border-radius: 3px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #007BFF;
}

/* Menu Bar styling */
QMenuBar {
    background-color: #F0F2F5;
    border-bottom: 1px solid #DCDCDC;
    padding: 2px;
}
QMenuBar::item {
    spacing: 4px;
    padding: 4px 10px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #E0E0E0;
}
QMenuBar::item:pressed {
    background: #007BFF;
    color: white;
}

/* Drop-down menu styling */
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #BDBDBD;
    padding: 5px;
}
QMenu::item {
    padding: 5px 25px 5px 20px;
    border: 1px solid transparent;
}
QMenu::item:selected {
    background-color: #007BFF;
    color: #FFFFFF;
}
QMenu::indicator:checked {
    background-color: #E0E0E0;
    height: 12px;
    width: 12px;
    margin-left: 5px;
}

/* SpinBox custom styling */
QSpinBox, QDoubleSpinBox { padding-right: 28px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
    width: 26px;
    subcontrol-origin: border;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right; top: 1px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right; bottom: 1px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #E0E0E0; border-radius: 3px;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(:/icons/plus.svg); width: 14px; height: 14px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(:/icons/minus.svg); width: 14px; height: 14px;
}
"""

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS_STYLE)

    # 1. 创建主窗口实例
    window = MainWindow()

    # 2. 调用新的方法来显示窗口并开始启动流程
    window.show_and_start_splash()

    # 3. 启动应用主循环
    sys.exit(app.exec())