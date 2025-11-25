# File: ui/widgets/channel_settings_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                             QLineEdit, QLabel, QScrollArea, QFrame)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from functools import partial


class ChannelRow(QWidget):
    """自定义的单行通道控件，封装了 Checkbox 和 Input"""

    def __init__(self, index, name, parent=None):
        super().__init__(parent)
        self.index = index

        layout = QHBoxLayout(self)
        # 减小上下边距，增加左右边距，让列表看起来更紧凑但宽敞
        layout.setContentsMargins(15, 4, 15, 4)
        layout.setSpacing(15)

        # 1. Checkbox (只负责开关)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        # 不需要设置固定宽度，让它自然适应

        # 2. (已删除) 序号标签 self.lbl_idx -> 删掉！冗余！

        # 3. 名称输入框 (更像文本的样式)
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Channel Name")
        self.name_edit.setMinimumHeight(28)
        # 使用样式表让它看起来更轻量：平时没有边框，鼠标悬停或聚焦时才显示
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: #37474F;
                font-weight: 500;
            }
            QLineEdit:hover {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
            }
            QLineEdit:focus {
                background-color: #FFFFFF;
                border: 1px solid #1A73E8;
                color: #000000;
            }
        """)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.name_edit)

        # 整个行的悬停效果
        self.setStyleSheet("""
            ChannelRow:hover { background-color: #F5F7FA; border-radius: 6px; }
        """)


class ChannelSettingsPanel(QWidget):
    channel_visibility_changed = pyqtSignal(int, bool)
    channel_name_changed = pyqtSignal(int, str)

    def __init__(self, num_channels=8, parent=None):
        super().__init__(parent)
        self.num_channels = 0
        self.rows = []

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")  # 透明背景

        # 内容容器
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(2)  # 行间距紧凑一点

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        self.reconfigure_channels(num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        if self.num_channels == num_channels: return
        self.num_channels = num_channels

        # 清空旧控件
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.rows = []

        # 生成新行
        for i in range(num_channels):
            row = ChannelRow(i, f"CH {i + 1}")

            # 连接信号
            # 注意 lambda 闭包陷阱，使用 default arg
            row.checkbox.stateChanged.connect(
                lambda state, idx=i: self.channel_visibility_changed.emit(idx, bool(state))
            )
            row.name_edit.editingFinished.connect(
                partial(self._on_name_changed, i)
            )

            self.content_layout.addWidget(row)
            self.rows.append(row)

        self.content_layout.addStretch()  # 底部弹簧

    def _on_name_changed(self, index):
        new_name = self.rows[index].name_edit.text()
        self.channel_name_changed.emit(index, new_name)

    def get_channel_names(self):
        return [row.name_edit.text() for row in self.rows]