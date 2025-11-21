# File: ui/widgets/recording_panel.py

from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton, QLineEdit
from PyQt6.QtCore import pyqtSignal, pyqtSlot


class RecordingPanel(QWidget):
    """
    一个独立的面板，包含所有与录制相关的控件和信号。
    """
    # 1. 定义本面板需要向外发射的信号
    start_recording_clicked = pyqtSignal()
    stop_recording_clicked = pyqtSignal()
    add_marker_clicked = pyqtSignal(str)
    open_file_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 2. 创建UI控件和布局
        rec_layout = QGridLayout(self)
        rec_layout.setContentsMargins(10, 10, 10, 10)
        rec_layout.setSpacing(8)  # 稍微减小间距

        self.start_rec_btn = QPushButton("Start Recording")
        self.stop_rec_btn = QPushButton("Stop Recording")
        self.marker_input = QLineEdit()
        self.marker_input.setPlaceholderText("Marker Label")  # 使用 PlaceholderText 体验更好
        self.add_marker_btn = QPushButton("Add Marker")
        self.open_btn = QPushButton("Open File")

        # 3. 连接内部控件的点击事件到本类的信号
        self.start_rec_btn.clicked.connect(self._on_start_recording)
        self.stop_rec_btn.clicked.connect(self._on_stop_recording)
        self.add_marker_btn.clicked.connect(self._on_add_marker)
        self.open_btn.clicked.connect(self.open_file_clicked.emit)

        # 4. 将控件添加到布局
        rec_layout.addWidget(self.start_rec_btn, 0, 0)
        rec_layout.addWidget(self.stop_rec_btn, 0, 1)
        rec_layout.addWidget(self.marker_input, 1, 0)
        rec_layout.addWidget(self.add_marker_btn, 1, 1)
        rec_layout.addWidget(self.open_btn, 2, 0, 1, 2)

        # 5. 初始化按钮状态
        self.set_session_active(False)  # 默认未连接状态
        self.set_recording_state(False)  # 默认未录制状态

    def _on_add_marker(self):
        marker_text = self.marker_input.text()
        if marker_text:
            self.add_marker_clicked.emit(marker_text)

    def _on_start_recording(self):
        self.set_recording_state(True)
        self.start_recording_clicked.emit()

    def _on_stop_recording(self):
        # 停止按钮按下后，暂时禁用所有按钮，等待MainWindow确认文件保存
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(False)
        self.add_marker_btn.setEnabled(False)
        self.stop_recording_clicked.emit()

    # --- 公共方法，供 MainWindow 调用 ---

    @pyqtSlot(bool)
    def set_session_active(self, is_active):
        """当连接/断开会话时调用"""
        self.open_btn.setEnabled(True)  # 打开文件按钮始终可用
        if is_active:
            self.start_rec_btn.setEnabled(True)
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)
        else:
            self.start_rec_btn.setEnabled(False)
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)

    @pyqtSlot(bool)
    def set_recording_state(self, is_recording):
        """当开始/停止录制或文件保存完成后调用"""
        self.start_rec_btn.setEnabled(not is_recording)
        self.stop_rec_btn.setEnabled(is_recording)
        self.add_marker_btn.setEnabled(is_recording)