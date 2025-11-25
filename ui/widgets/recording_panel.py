# File: ui/widgets/recording_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt


class RecordingPanel(QWidget):
    start_recording_clicked = pyqtSignal()
    stop_recording_clicked = pyqtSignal()
    add_marker_clicked = pyqtSignal(str)
    open_file_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- 1. 录制控制区 (并排) ---
        rec_ctrl_layout = QHBoxLayout()

        self.start_rec_btn = QPushButton("Start Record")
        self.start_rec_btn.setObjectName("btnStart")  # 绿色
        self.start_rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_rec_btn.setFixedHeight(36)

        self.stop_rec_btn = QPushButton("Stop")
        self.stop_rec_btn.setObjectName("btnStop")  # 红色
        self.stop_rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_rec_btn.setFixedHeight(36)

        rec_ctrl_layout.addWidget(self.start_rec_btn)
        rec_ctrl_layout.addWidget(self.stop_rec_btn)
        main_layout.addLayout(rec_ctrl_layout)

        # --- 2. 标记区 (Marker) ---
        marker_layout = QHBoxLayout()

        self.marker_input = QLineEdit()
        self.marker_input.setPlaceholderText("Event Label (e.g. 'Eyes Closed')")
        self.marker_input.setMinimumHeight(32)

        self.add_marker_btn = QPushButton("Add Marker")
        self.add_marker_btn.setObjectName("btnAdd")  # 蓝色
        self.add_marker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_marker_btn.setFixedHeight(32)

        marker_layout.addWidget(self.marker_input, stretch=1)
        marker_layout.addWidget(self.add_marker_btn)
        main_layout.addLayout(marker_layout)

        # --- 分隔线 (可选) ---
        # line = QFrame()
        # line.setFrameShape(QFrame.Shape.HLine)
        # line.setStyleSheet("color: #DADCE0;")
        # main_layout.addWidget(line)

        # --- 3. 文件操作区 ---
        self.open_btn = QPushButton("Open Existing File")
        self.open_btn.setObjectName("btnNormal")  # 白色/灰色
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setFixedHeight(36)

        main_layout.addWidget(self.open_btn)
        main_layout.addStretch()  # 顶上去

        # --- 信号连接 ---
        self.start_rec_btn.clicked.connect(self._on_start_recording)
        self.stop_rec_btn.clicked.connect(self._on_stop_recording)
        self.add_marker_btn.clicked.connect(self._on_add_marker)
        self.open_btn.clicked.connect(self.open_file_clicked.emit)

        # 回车添加 Marker
        self.marker_input.returnPressed.connect(self._on_add_marker)

        self.set_session_active(False)
        self.set_recording_state(False)

    def _on_add_marker(self):
        text = self.marker_input.text().strip()
        if text:
            self.add_marker_clicked.emit(text)
            self.marker_input.clear()  # 添加后清空

    def _on_start_recording(self):
        self.set_recording_state(True)
        self.start_recording_clicked.emit()

    def _on_stop_recording(self):
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(False)
        self.add_marker_btn.setEnabled(False)
        self.stop_recording_clicked.emit()

    @pyqtSlot(bool)
    def set_session_active(self, is_active):
        self.open_btn.setEnabled(True)
        if is_active:
            self.start_rec_btn.setEnabled(True)
            self.stop_rec_btn.setEnabled(False)  # 初始未录制，所以Stop禁用
            self.add_marker_btn.setEnabled(False)
            self.marker_input.setEnabled(False)
        else:
            self.start_rec_btn.setEnabled(False)
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)
            self.marker_input.setEnabled(False)

    @pyqtSlot(bool)
    def set_recording_state(self, is_recording):
        self.start_rec_btn.setEnabled(not is_recording)
        self.stop_rec_btn.setEnabled(is_recording)
        self.add_marker_btn.setEnabled(is_recording)
        self.marker_input.setEnabled(is_recording)