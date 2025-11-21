# File: ui/widgets/channel_settings_panel.py

from PyQt6.QtWidgets import QWidget, QGridLayout, QCheckBox, QLineEdit
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from functools import partial


class ChannelSettingsPanel(QWidget):
    """
    一个独立的面板，用于控制各个通道的可见性和名称。
    """
    # 1. 定义信号
    channel_visibility_changed = pyqtSignal(int, bool)
    channel_name_changed = pyqtSignal(int, str)

    def __init__(self, num_channels=8, parent=None):
        super().__init__(parent)

        self.num_channels = 0  # 初始为0，强制reconfigure执行
        self.ch_checkboxes = []
        self.ch_name_edits = []

        # 2. 创建主布局
        self.ch_layout = QGridLayout(self)
        self.ch_layout.setContentsMargins(10, 10, 10, 10)
        self.ch_layout.setSpacing(8)

        # 3. 初始化UI
        self.reconfigure_channels(num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        if self.num_channels == num_channels:
            return

        self.num_channels = num_channels

        # 清空旧的UI组件
        while self.ch_layout.count():
            item = self.ch_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.ch_checkboxes = []
        self.ch_name_edits = []

        # 重新创建UI组件
        for i in range(num_channels):
            checkbox = QCheckBox(checked=True)
            checkbox.setToolTip(f"Toggle visibility for Channel {i + 1}")
            checkbox.stateChanged.connect(lambda state, ch=i: self.channel_visibility_changed.emit(ch, bool(state)))

            name_edit = QLineEdit(f"CH {i + 1}")
            name_edit.editingFinished.connect(partial(self._on_name_changed, i))

            self.ch_layout.addWidget(checkbox, i, 0)
            self.ch_layout.addWidget(name_edit, i, 1)

            self.ch_checkboxes.append(checkbox)
            self.ch_name_edits.append(name_edit)

        self.ch_layout.setColumnStretch(0, 0)
        self.ch_layout.setColumnStretch(1, 1)

    def _on_name_changed(self, channel_index):
        new_name = self.ch_name_edits[channel_index].text()
        self.channel_name_changed.emit(channel_index, new_name)

    def get_channel_names(self):
        """返回所有通道当前名称的列表"""
        return [edit.text() for edit in self.ch_name_edits]