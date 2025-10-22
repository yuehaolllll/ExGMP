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
    background-color: #F0F2F5; /* A very light, neutral gray background */
    color: #212121;           /* Dark gray text for high readability */
    font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 10pt;
}

/* GroupBox styling */
QGroupBox {
    background-color: #FFFFFF; /* White background for containers */
    border: 1px solid #DCDCDC; /* Subtle gray border */
    border-radius: 6px;
    margin-top: 1ex;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 2px 8px;
    color: #005A9E; /* Professional blue for titles */
}

/* Button styling */
QPushButton {
    background-color: #E0E0E0; /* Standard light gray button */
    border: 1px solid #BDBDBD;
    padding: 6px 12px;
    border-radius: 4px;
    color: #212121;
}
QPushButton:hover {
    background-color: #E8E8E8;
    border: 1px solid #007BFF; /* Blue highlight on hover */
}
QPushButton:pressed {
    background-color: #D0D0D0; /* Darker gray when pressed */
}
QPushButton:disabled {
    background-color: #F5F5F5;
    color: #BDBDBD;
}

/* Primary action buttons (Connect, Start) */
QPushButton#primary_button {
    background-color: #007BFF; /* Bright blue for primary actions */
    color: #FFFFFF;
    font-weight: bold;
    border: none;
}
QPushButton#primary_button:hover {
    background-color: #0056b3;
}
QPushButton#primary_button:pressed {
    background-color: #004085;
}

/* Secondary/danger buttons (Disconnect, Stop) */
QPushButton#secondary_button {
    background-color: #DC3545; /* Standard red for danger actions */
    color: #FFFFFF;
    font-weight: bold;
    border: none;
}
QPushButton#secondary_button:hover {
    background-color: #c82333;
}
QPushButton#secondary_button:pressed {
    background-color: #bd2130;
}

/* Input fields styling */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #BDBDBD;
    border-radius: 4px;
    padding: 5px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #007BFF; /* Blue highlight on focus */
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

/* Status Label */
#status_label {
    font-style: italic;
    color: #6c757d; /* Muted gray for status text */
}

/* Menu Bar styling */
QMenuBar {
    background-color: #F0F2F5; /* 与主背景色相同 */
    border-bottom: 1px solid #DCDCDC; /* 在菜单栏底部添加一条细边框 */
    padding: 2px;
}

QMenuBar::item {
    spacing: 4px;
    padding: 4px 10px;
    background: transparent;
    border-radius: 4px;
}

QMenuBar::item:selected { /* 当鼠标悬停在菜单项上时 */
    background: #E0E0E0;
}

QMenuBar::item:pressed { /* 当菜单被点击并打开时 */
    background: #007BFF;
    color: white;
}

/* Drop-down menu styling */
QMenu {
    background-color: #FFFFFF; /* 下拉菜单使用白色背景 */
    border: 1px solid #BDBDBD;
    padding: 5px;
}

QMenu::item {
    padding: 5px 25px 5px 20px;
    border: 1px solid transparent; /* 为选中效果留出空间 */
}

QMenu::item:selected { /* 当鼠标悬停在下拉菜单的某个动作上时 */
    background-color: #007BFF;
    color: #FFFFFF;
}

/* 为可勾选的菜单项添加一个“勾”的图标 */
QMenu::indicator:checked {
    /* 这里你可以放置一个 check.svg 图标 */
    /* image: url(:/icons/check.svg); */
    background-color: #E0E0E0;
    height: 12px;
    width: 12px;
    margin-left: 5px;
}

/* SpinBox custom styling */
QSpinBox, QDoubleSpinBox {
    /* 为按钮留出空间 */
    padding-right: 28px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    /* 移除默认的边框和背景 */
    border: none;
    background: transparent;
    /* 定义按钮的尺寸和位置 */
    width: 26px;
    subcontrol-origin: border;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right;
    top: 1px; /* 微调位置 */
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right;
    bottom: 1px; /* 微调位置 */
}

/* 当鼠标悬停在按钮上时的效果 */
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #E0E0E0; /* 与普通按钮悬停色一致 */
    border-radius: 3px;
}

/* 定义上下箭头的图标 */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(:/icons/plus.svg);
    width: 14px;
    height: 14px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(:/icons/minus.svg);
    width: 14px;
    height: 14px;
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