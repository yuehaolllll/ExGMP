# File: ui/widgets/recording_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFrame)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer


class RecordingPanel(QWidget):
    start_recording_clicked = pyqtSignal()
    stop_recording_clicked = pyqtSignal()
    add_marker_clicked = pyqtSignal(str)
    open_file_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 样式表优化 ---
        self.setStyleSheet("""
            /* 1. 标记按钮 (Marker) - 深青色 */
            QPushButton#btnMarker {
                background-color: #009688; 
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 0 10px; /* 减小左右padding，防止文字被挤 */
            }
            QPushButton#btnMarker:hover { background-color: #00796B; }
            QPushButton#btnMarker:pressed { background-color: #004D40; }
            QPushButton#btnMarker:disabled { background-color: #E0E0E0; color: #9E9E9E; }

            /* 2. 开始按钮 (Start) - 蓝色 */
            QPushButton#btnStart {
                background-color: #1A73E8;
                color: white; border: none; border-radius: 4px; font-weight: bold;
            }
            QPushButton#btnStart:hover { background-color: #1557B0; }

            /* 录制中状态 (淡蓝背景+深蓝字) */
            QPushButton#btnStart:disabled {
                background-color: #E8F0FE; 
                color: #1A73E8; 
                border: 1px solid #1A73E8;
            }

            /* 3. 停止按钮 (Stop) - 红色 */
            QPushButton#btnStop {
                background-color: #EA4335; 
                color: white; border: none; border-radius: 4px; font-weight: bold;
            }
            QPushButton#btnStop:hover { background-color: #D32F2F; }
            QPushButton#btnStop:disabled { background-color: #FCE8E6; color: #EA4335; border: 1px solid #EA4335; opacity: 0.6;}

            /* 4. 打开文件按钮 (Open) - 紫色 */
            QPushButton#btnOpen {
                background-color: #673AB7; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton#btnOpen:hover { background-color: #5E35B1; }
            QPushButton#btnOpen:pressed { background-color: #4527A0; }
            QPushButton#btnOpen:disabled { background-color: #F3E5F5; color: #B39DDB; border: 1px solid #D1C4E9; }

            /* 5. 输入框样式 */
            QLineEdit {
                background-color: #F8F9FA;
                border: 1px solid #DADCE0;
                border-radius: 4px;
                padding: 4px 8px;
                color: #3C4043;
            }
            QLineEdit:focus { border: 2px solid #1A73E8; background-color: #FFFFFF; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- 1. 录制控制区 ---
        rec_ctrl_layout = QHBoxLayout()
        rec_ctrl_layout.setSpacing(10)

        self.start_rec_btn = QPushButton("Start Record")
        self.start_rec_btn.setObjectName("btnStart")
        self.start_rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_rec_btn.setFixedHeight(38)

        self.stop_rec_btn = QPushButton("Stop")
        self.stop_rec_btn.setObjectName("btnStop")
        self.stop_rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_rec_btn.setFixedHeight(38)

        rec_ctrl_layout.addWidget(self.start_rec_btn)
        rec_ctrl_layout.addWidget(self.stop_rec_btn)
        main_layout.addLayout(rec_ctrl_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #E0E0E0; margin: 5px 0;")
        line.setFixedHeight(1)
        main_layout.addWidget(line)

        # --- 2. 标记区 (Marker) ---
        marker_layout = QHBoxLayout()
        marker_layout.setSpacing(8)

        self.marker_input = QLineEdit()
        self.marker_input.setPlaceholderText("Event Label (e.g. 'Eyes Closed')")
        self.marker_input.setMinimumHeight(32)

        self.add_marker_btn = QPushButton("Marker")
        self.add_marker_btn.setObjectName("btnMarker")
        self.add_marker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 关键修复：移除固定宽度，改用最小宽度，让文字完整显示
        self.add_marker_btn.setMinimumWidth(80)
        self.add_marker_btn.setFixedHeight(32)

        marker_layout.addWidget(self.marker_input)
        marker_layout.addWidget(self.add_marker_btn)
        main_layout.addLayout(marker_layout)

        # --- 3. 文件操作区 ---
        self.open_btn = QPushButton("Open Existing File")
        self.open_btn.setObjectName("btnOpen")  # 使用新的紫色样式
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setFixedHeight(38)  # 稍微加高

        main_layout.addWidget(self.open_btn)
        main_layout.addStretch()

        # --- 信号连接 ---
        self.start_rec_btn.clicked.connect(self._on_start_recording)
        self.stop_rec_btn.clicked.connect(self._on_stop_recording)
        self.add_marker_btn.clicked.connect(self._on_add_marker)
        self.open_btn.clicked.connect(self.open_file_clicked.emit)
        self.marker_input.returnPressed.connect(self._on_add_marker)

        # 初始状态
        self.set_session_active(False)
        self.set_recording_state(False)

    def _on_add_marker(self):
        text = self.marker_input.text().strip()
        if text:
            self.add_marker_clicked.emit(text)
            self.marker_input.clear()
            orig_text = self.add_marker_btn.text()
            self.add_marker_btn.setText("Added!")
            QTimer.singleShot(800, lambda: self.add_marker_btn.setText(orig_text))

    def _on_start_recording(self):
        self.start_rec_btn.setText("Recording...")
        self.set_recording_state(True)
        self.start_recording_clicked.emit()

    def _on_stop_recording(self):
        self.start_rec_btn.setText("Start Record")
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(False)
        self.add_marker_btn.setEnabled(False)
        self.stop_recording_clicked.emit()

    @pyqtSlot(bool)
    def set_session_active(self, is_active):
        self.open_btn.setEnabled(True)
        if is_active:
            self.start_rec_btn.setEnabled(True)
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)
            self.marker_input.setEnabled(False)
            self.start_rec_btn.setText("Start Record")
        else:
            self.start_rec_btn.setEnabled(False)
            self.stop_rec_btn.setEnabled(False)
            self.add_marker_btn.setEnabled(False)
            self.marker_input.setEnabled(False)
            self.start_rec_btn.setText("Start Record")

    @pyqtSlot(bool)
    def set_recording_state(self, is_recording):
        self.start_rec_btn.setEnabled(not is_recording)
        self.stop_rec_btn.setEnabled(is_recording)
        self.add_marker_btn.setEnabled(is_recording)
        self.marker_input.setEnabled(is_recording)

        if is_recording:
            self.marker_input.setFocus()