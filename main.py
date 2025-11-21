import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

# 尝试导入编译后的资源文件 (resources_rc.py)
# 如果你使用了 .qrc 文件并通过 pyrcc6 编译，这将允许 QSS 中的 url(:/icons/...) 生效
try:
    import resources_rc
except ImportError:
    pass

# --- 环境兼容性修复 ---
# 解决 Windows 下 Conda 环境可能出现的 DLL 加载错误，以及 PyInstaller 打包后的路径问题
try:
    if 'CONDA_PREFIX' in os.environ:
        conda_prefix = os.environ['CONDA_PREFIX']
        # 添加 Library/bin 到 DLL 搜索路径 (针对 Windows)
        if os.name == 'nt':
            os.add_dll_directory(os.path.join(conda_prefix, 'Library', 'bin'))

    # 处理 PyInstaller 的临时目录
    if hasattr(sys, '_MEIPASS'):
        if os.name == 'nt':
            os.add_dll_directory(sys._MEIPASS)

    # 解决某些库 (如 numpy/torch) 的 OpenMP 冲突报错
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
except Exception:
    pass


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# --- 全局样式表 (QSS) ---
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

QMenu::item:disabled {
    color: #BDBDBD;
    background: transparent;
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

/* 注意：如果你没有编译 resources.qrc，下面这两行可能会在控制台报警告，但不影响运行 */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(:/icons/plus.svg); width: 14px; height: 14px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(:/icons/minus.svg); width: 14px; height: 14px;
}
"""

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 应用全局样式表
    app.setStyleSheet(QSS_STYLE)

    # 1. 创建主窗口实例
    window = MainWindow()

    # 2. 调用我们在第一部分添加的方法：显示窗口并开始 Splash 动画
    # 这会让窗口居中并自适应屏幕大小
    window.show_and_start_splash()

    # 3. 启动应用主循环
    sys.exit(app.exec())