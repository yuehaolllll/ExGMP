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
/* --- Google Material Design Theme (PNG Compatible Edition) --- */

/* 1. 全局基础 */
QWidget {
    background-color: #FFFFFF;
    color: #202124;
    font-family: "Segoe UI", "Roboto", "Microsoft YaHei", sans-serif;
    font-size: 10pt;
}

/* 2. 分组框 */
QGroupBox {
    background-color: transparent;
    border: 1px solid #DADCE0;
    border-radius: 8px;
    margin-top: 24px;
    font-weight: 500;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
    color: #1A73E8;
    background-color: #FFFFFF;
}

/* 3. 单选框 (Radio) */
QRadioButton {
    spacing: 8px; padding: 6px 10px; border-radius: 4px; color: #3C4043; font-weight: 400;
}
QRadioButton:hover { background-color: #F1F3F4; }
QRadioButton:checked { background-color: #E8F0FE; color: #1967D2; font-weight: 600; }

QRadioButton::indicator {
    width: 16px; height: 16px;
    border-radius: 9px;
    background-color: #FFFFFF;
    image: none;
}
QRadioButton::indicator:unchecked { border: 2px solid #5F6368; }
QRadioButton::indicator:unchecked:hover { border-color: #1A73E8; background-color: #F8F9FA; }
QRadioButton::indicator:checked {
    border: 5px solid #1A73E8;
    background-color: #FFFFFF;
}

/* 4. 复选框 (CheckBox) - 修复对号显示 */
QCheckBox {
    spacing: 10px; color: #3C4043; font-weight: 400;
}
QCheckBox:hover { background-color: transparent; }

QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 3px;
    border: 2px solid #5F6368;
    background-color: #FFFFFF;
}
QCheckBox::indicator:hover { border-color: #1A73E8; background-color: #F8F9FA; }

QCheckBox::indicator:checked {
    background-color: #1A73E8;
    border: 2px solid #1A73E8;
    /* PNG 格式的白色对号，保证显示 */
    image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAUElEQVQokWNgIBEwMjAw/AdxSRiI8AmD5DDAXFw6//9H1gUTx6UDRANMHAuA62VkwC5xH6c4yDhuA3ApRrYAm2I8DoO04XYg3mDE6S2cHgMNAQCUyR117g55OAAAAABJRU5ErkJggg==);
}

/* 5. 按钮 */
QPushButton {
    border-radius: 4px; padding: 8px 24px; font-weight: 600; font-size: 10pt; border: 1px solid transparent;
}
QPushButton#btnConnect, QPushButton#btnStart, QPushButton#btnAdd {
    background-color: #1A73E8; color: white; border: none;
}
QPushButton#btnConnect:hover, QPushButton#btnStart:hover, QPushButton#btnAdd:hover {
    background-color: #185ABC;
}
QPushButton#btnConnect:pressed, QPushButton#btnStart:pressed, QPushButton#btnAdd:pressed {
    background-color: #174EA6;
}
QPushButton#btnConnect:disabled {
    background-color: #F1F3F4; color: #BDC1C6;
}
QPushButton#btnStop {
    background-color: #EA4335; color: white; border: none;
}
QPushButton#btnStop:hover { background-color: #D32F2F; }

QPushButton#btnDisconnect, QPushButton#btnNormal, QPushButton#btnViewSwitch {
    background-color: #FFFFFF; border: 1px solid #DADCE0; color: #1A73E8;
}
QPushButton#btnDisconnect:hover, QPushButton#btnNormal:hover, QPushButton#btnViewSwitch:hover {
    background-color: #F8F9FA; border-color: #1A73E8;
}
QPushButton#btnDisconnect:pressed { background-color: #E8F0FE; }

/* 6. 下拉框 (ComboBox) - 布局修复版 */
QComboBox {
    background-color: #F1F3F4;
    border: 1px solid transparent; /* 显式设置边框，辅助定位 */
    border-radius: 4px;
    padding: 6px 10px;
    padding-right: 35px; /* 必须大于 drop-down 的宽度 */
    color: #202124;
    min-height: 24px;
}
QComboBox:hover {
    background-color: #E8EAED;
    border-bottom: 1px solid #5F6368;
}
QComboBox:on {
    background-color: #E8F0FE;
    border-bottom: 2px solid #1A73E8;
}

/* 下拉按钮区域 - 增加背景色以确保可见 */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    
    border-left-width: 0px;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background-color: transparent; /* 默认透明，悬停变色 */
}
QComboBox::drop-down:hover {
    background-color: #D2E3FC; /* 鼠标悬停时显示淡蓝色背景 */
}

/* 下箭头 - 确保居中 */
QComboBox::down-arrow {
    width: 12px;
    height: 12px;
    /* 加上引号，并使用一个肯定能用的黑色箭头 Base64 */
    image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAR0lEQVQokWNgwA34g/j/cfD/URQ5BswE6ccw4n/K4P+4xHE5B8QA6cexAfgVw+T/45f3f0wY3XZ0A/Ar/o9i4P9RDPzHqgAAkP52BOQy+mAAAAAASUVORK5CYII=");
}


/* --- 7. 数值输入框 (SpinBox) - 强力修复版 --- */
QSpinBox, QDoubleSpinBox {
    background-color: #F1F3F4;
    border: 1px solid transparent;
    border-radius: 4px;
    color: #202124;
    min-height: 30px;
    padding-right: 30px; /* 为右侧按钮留出空间 */
    padding-left: 10px;
}
QSpinBox:hover, QDoubleSpinBox:hover {
    background-color: #E8EAED;
    border-bottom: 1px solid #5F6368;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    background-color: #FFFFFF;
    border-bottom: 2px solid #1A73E8;
}

/* 按钮区域通用设置 */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; /* 使用 border 盒模型定位 */
    width: 28px; /* 略小于 padding-right */
    border-left: 1px solid #DADCE0; /* 加上左边框 */
    background-color: #F8F9FA; /* 给按钮一个默认背景色，防止“消失” */
}

/* 上按钮 */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right; /* 绝对定位到右上角 */
    height: 15px; /* 高度的一半 */
    border-top-right-radius: 4px;
    margin-bottom: 0px;
}

/* 下按钮 */
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right; /* 绝对定位到右下角 */
    height: 15px;
    border-bottom-right-radius: 4px;
    margin-top: 0px;
}

/* 按钮悬停/按下效果 */
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #D2E3FC;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #1A73E8;
}

/* 箭头图标 - 使用加引号的 Base64 */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 8px;
    height: 8px;
    image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAN0lEQVQokWNgwA34g/j/cfD/URQ5BswE6ccw4n/K4P+4xHE5B8QA6cexAfgVw+T/45f3f0wY3XYAp95yBO084/AAAAAASUVORK5CYII=");
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 8px;
    height: 8px;
    image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAMCAYAAABWdVznAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAR0lEQVQokWNgwA34g/j/cfD/URQ5BswE6ccw4n/K4P+4xHE5B8QA6cexAfgVw+T/45f3f0wY3XZ0A/Ar/o9i4P9RDPzHqgAAkP52BOQy+mAAAAAASUVORK5CYII=");
}

/* 箭头在按钮被按下时变白 (可选) */
QSpinBox::up-button:pressed::up-arrow, QDoubleSpinBox::up-button:pressed::up-arrow,
QSpinBox::down-button:pressed::down-arrow, QDoubleSpinBox::down-button:pressed::down-arrow {
    /* 这里可以使用滤镜或者换一个白色的图片，为简单起见暂时不换图片，主要保证结构正确 */
}

/* 8. 其他 */
QLabel { color: #5F6368; font-weight: 500; }
QMenuBar { background-color: #FFFFFF; border-bottom: 1px solid #DADCE0; }
QMenuBar::item { color: #5F6368; padding: 8px 12px; background: transparent; }
QMenuBar::item:selected { background-color: #F1F3F4; color: #202124; border-radius: 4px; }
QMenu { background-color: #FFFFFF; border: 1px solid #DADCE0; padding: 8px 0; border-radius: 8px; }
QMenu::item { padding: 8px 32px 8px 16px; color: #3C4043; }
QMenu::item:selected { background-color: #E8F0FE; color: #1967D2; }
"""

if __name__ == '__main__':
    #app.setStyle('Windows')
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