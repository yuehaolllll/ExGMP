# File: ui/widgets/channel_settings_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                             QLineEdit, QLabel, QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QSize
from functools import partial


class ChannelRow(QWidget):
    """自定义的单行通道控件，封装了 Checkbox 和 Input"""

    def __init__(self, index, name, parent=None):
        super().__init__(parent)
        self.index = index

        # 行布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(12)

        # 1. Checkbox (纯 CSS 手绘风格)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        self.checkbox.setStyleSheet("""
            QCheckBox { spacing: 0px; }
            QCheckBox::indicator { 
                width: 18px; height: 18px; 
                border: 2px solid #BDBDBD; 
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:hover { border-color: #1A73E8; }
            QCheckBox::indicator:checked {
                background-color: #1A73E8;
                border: 2px solid #1A73E8;
                image: none; 
            }
            QCheckBox::indicator:checked:hover {
                background-color: #1557B0;
                border-color: #1557B0;
            }
        """)

        # 2. 名称输入框
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Channel Name")
        self.name_edit.setMinimumHeight(32)

        self.name_edit.setStyleSheet("""
            QLineEdit {
                background: #F5F5F5; 
                border: 1px solid transparent;
                border-bottom: 1px solid #E0E0E0;
                border-radius: 4px;
                color: #37474F;
                font-weight: 500;
                padding-left: 8px;
                selection-background-color: #1A73E8;
            }
            QLineEdit:hover {
                background-color: #FFFFFF;
                border: 1px solid #BDBDBD;
            }
            QLineEdit:focus {
                background-color: #FFFFFF;
                border: 2px solid #1A73E8;
                color: #000000;
            }
        """)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.name_edit)

        # 行悬停效果
        self.setStyleSheet("""
            ChannelRow:hover { background-color: #F1F3F4; border-radius: 6px; }
        """)


class ChannelSettingsPanel(QWidget):
    channel_visibility_changed = pyqtSignal(int, bool)
    channel_name_changed = pyqtSignal(int, str)

    def __init__(self, num_channels=8, parent=None):
        super().__init__(parent)
        self.num_channels = 0
        self.rows = []

        # 允许面板随内容伸缩
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # 关键：允许内部 Widget 决定大小
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动条样式优化
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }

            QScrollBar:vertical {
                border: none;
                background: #F1F1F1; /* 浅灰槽背景，提示可以滚动 */
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        # 内容容器
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(5, 10, 5, 10)
        self.content_layout.setSpacing(4)
        # 关键：让布局紧凑，对齐顶部，不要均匀分布
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        self.reconfigure_channels(num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        if self.num_channels == num_channels: return
        self.num_channels = num_channels

        # 清空旧行
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.rows = []

        # 添加新行
        for i in range(num_channels):
            row = ChannelRow(i, f"CH {i + 1}")
            row.checkbox.stateChanged.connect(
                lambda state, idx=i: self.channel_visibility_changed.emit(idx, bool(state))
            )
            row.name_edit.editingFinished.connect(
                partial(self._on_name_changed, i)
            )
            self.content_layout.addWidget(row)
            self.rows.append(row)

        # 这里不再添加 addStretch()，依靠 setAlignment(AlignTop) 保持紧凑

        # 【核心步骤】通知 Qt 布局系统尺寸已改变
        self.updateGeometry()
        self.adjustSize()

    def sizeHint(self):
        """
        动态计算高度：
        - 如果内容较少，高度刚好包裹内容 (无留白)。
        - 如果内容较多，高度限制在 400px，出现滚动条。
        """
        # 估算每行高度：32px(输入框) + 4px(间距) + 4px(上下padding) ≈ 40px
        row_height_est = 40
        margins = 20  # 容器的上下 margin

        calculated_height = (self.num_channels * row_height_est) + margins

        # 限制最大高度 (例如 400px)，超过则出现滚动条
        max_height = 400

        final_height = min(calculated_height, max_height)

        # 宽度保持固定
        return QSize(250, final_height)

    def _on_name_changed(self, index):
        new_name = self.rows[index].name_edit.text()
        self.channel_name_changed.emit(index, new_name)

    def get_channel_names(self):
        return [row.name_edit.text() for row in self.rows]