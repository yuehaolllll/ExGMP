from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSlot, QPropertyAnimation, QPoint, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor

from processing.acquisition_controller import AcquisitionState


class GuidanceOverlay(QWidget):
    """
    一个独立的、顶级的、真正的全屏覆盖层。
    """
    exit_clicked = pyqtSignal()
    def __init__(self, parent=None):
        # 注意：parent 将为 None，因为它是一个顶级窗口
        super().__init__(parent)

        # --- 核心修改 1：设置顶级窗口的属性 ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # 1. 无边框
            Qt.WindowType.WindowStaysOnTopHint |  # 2. 始终保持在最顶层
            Qt.WindowType.Tool  # 3. 不在任务栏显示图标
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 1. 创建主垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)  # 在屏幕边缘留出一点边距

        # 2. 创建并添加顶部栏布局
        top_bar_layout = QHBoxLayout()
        self.exit_button = QPushButton("× Abort")
        self.exit_button.setFixedSize(100, 40)
        self.exit_button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 255, 255, 0.2); color: white;
                        border: 1px solid white; border-radius: 8px; font-size: 14px;
                    }
                    QPushButton:hover { background-color: rgba(255, 255, 255, 0.4); }
                    QPushButton:pressed { background-color: rgba(220, 53, 69, 0.8); }
                """)
        self.exit_button.clicked.connect(self.exit_clicked.emit)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.exit_button)
        main_layout.addLayout(top_bar_layout)  # 将顶部栏添加到主布局

        # 3. 创建并添加中间内容布局
        content_layout = QVBoxLayout()
        self.instruction_label = QLabel()
        font = QFont();
        font.setPointSize(200);
        font.setBold(True)
        self.instruction_label.setFont(font)
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setStyleSheet(
            "color: white; background-color: transparent; text-shadow: 5px 5px 10px black;")
        self.instruction_label.setWordWrap(True)

        self.sub_label = QLabel()
        font.setPointSize(100);
        font.setBold(False)
        self.sub_label.setFont(font)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("color: #DDDDDD; background-color: transparent;")
        self.sub_label.setWordWrap(True)

        content_layout.addStretch()
        content_layout.addWidget(self.instruction_label)
        content_layout.addWidget(self.sub_label)
        content_layout.addStretch()
        main_layout.addLayout(content_layout, stretch=1)  # 将内容区添加到主布局，并让它占据所有剩余空间

        # --- (刺激点和动画的创建代码不变) ---
        self.stimulus_dot = QWidget(self)
        self.stimulus_dot.setFixedSize(60, 60)
        self.stimulus_dot.setStyleSheet("background-color: #FFEB3B; border-radius: 30px; border: 2px solid white;")
        self.stimulus_dot.hide()
        self.animation = QPropertyAnimation(self.stimulus_dot, b"pos")
        self.animation.setDuration(1500)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.hide()

    def paintEvent(self, event):
        """手动绘制半透明黑色背景"""
        painter = QPainter(self)
        painter.setBrush(QColor(0, 0, 0, 217))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

    def show_overlay(self):
        """核心修改 2：使用 showFullScreen() 来显示"""
        self.showFullScreen()
        self.raise_()

    # --- (update_display, hide_overlay, _start_stimulus_animation 方法保持不变) ---
    @pyqtSlot(AcquisitionState, object)
    def update_display(self, state, data):
        self.stimulus_dot.hide()
        self.instruction_label.setText("")
        self.sub_label.setText("")
        if state == AcquisitionState.INSTRUCT:
            self.instruction_label.setText(str(data))
        elif state == AcquisitionState.COUNTDOWN:
            self.instruction_label.setText(str(data))
            self.sub_label.setText("Get Ready...")
        elif state == AcquisitionState.RECORDING:
            action_text = str(data).replace('_', ' ').title()
            if str(data) == 'BLINK':
                self.instruction_label.setText("Blink Normally")
            else:
                self.sub_label.setText(action_text)
            self._start_stimulus_animation(str(data))
        elif state == AcquisitionState.REST:
            self.instruction_label.setText(str(data))

    def hide_overlay(self):
        self.hide()

    def _start_stimulus_animation(self, action):
        if action not in ['UP', 'DOWN', 'LEFT', 'RIGHT']: return
        center_pos = self.rect().center() - self.stimulus_dot.rect().center()
        self.stimulus_dot.move(center_pos)
        self.stimulus_dot.show()
        if action == 'UP':
            target_pos = QPoint(center_pos.x(), 80)
        elif action == 'DOWN':
            target_pos = QPoint(center_pos.x(), self.height() - 140)
        elif action == 'LEFT':
            target_pos = QPoint(80, center_pos.y())
        elif action == 'RIGHT':
            target_pos = QPoint(self.width() - 140, center_pos.y())
        self.animation.setStartValue(center_pos)
        self.animation.setEndValue(target_pos)
        self.animation.start()