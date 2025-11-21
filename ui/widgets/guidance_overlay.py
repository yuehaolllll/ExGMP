from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSlot, QPropertyAnimation, QPoint, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from processing.acquisition_controller import AcquisitionState


class GuidanceOverlay(QWidget):
    """
    全屏引导遮罩层。
    提供半透明背景、指令文字显示以及眼动诱导动画。
    """
    exit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        # parent 必须为 None 以便全屏覆盖
        super().__init__(None)

        # --- 窗口属性设置 ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # 无边框
            Qt.WindowType.WindowStaysOnTopHint |  # 最顶层
            Qt.WindowType.Tool  # 不显示任务栏图标
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 确保鼠标事件穿透 (可选，如果希望点击背景不拦截，可以开启 TransparentForMouseEvents)
        # 但这里我们需要拦截鼠标以防止误操作到底层窗口，除了退出按钮。
        # self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # --- UI 布局 ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # 1. 顶部栏 (退出按钮)
        top_bar_layout = QHBoxLayout()
        self.exit_button = QPushButton("× Abort Session")
        self.exit_button.setFixedSize(140, 45)
        self.exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.3); 
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.6); 
                border-radius: 5px; 
                font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { 
                background-color: rgba(220, 53, 69, 0.8); 
                border-color: #dc3545;
            }
        """)
        self.exit_button.clicked.connect(self.exit_clicked.emit)

        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.exit_button)
        main_layout.addLayout(top_bar_layout)

        # 2. 中间内容区 (指令文字)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(20)

        self.instruction_label = QLabel()
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setStyleSheet("""
            color: white; 
            background-color: transparent; 
            font-size: 64px; 
            font-weight: bold;
        """)
        self.instruction_label.setWordWrap(True)

        # 给主文字加一点阴影效果，防止背景太亮看不清
        shadow = QGraphicsOpacityEffect(self)
        shadow.setOpacity(
            1.0)  # 这里仅作为占位，实际阴影通常用 QGraphicsDropShadowEffect，但简单样式表 text-shadow 在 QLabel 有时不支持，这里保留你的样式表做法即可

        self.sub_label = QLabel()
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("""
            color: #E0E0E0; 
            background-color: transparent;
            font-size: 32px;
            font-weight: normal;
        """)
        self.sub_label.setWordWrap(True)

        content_layout.addStretch()
        content_layout.addWidget(self.instruction_label)
        content_layout.addWidget(self.sub_label)
        content_layout.addStretch()

        main_layout.addLayout(content_layout, stretch=1)

        # --- 诱导动画小球 ---
        self.dot_size = 50
        self.stimulus_dot = QWidget(self)
        self.stimulus_dot.setFixedSize(self.dot_size, self.dot_size)
        # 黄色圆点，带白色边框，高对比度
        self.stimulus_dot.setStyleSheet(f"""
            background-color: #FFFF00; 
            border-radius: {self.dot_size // 2}px; 
            border: 3px solid white;
        """)
        self.stimulus_dot.hide()

        # 动画设置
        self.animation = QPropertyAnimation(self.stimulus_dot, b"pos")
        # 时间要与 AcquisitionController 中的 RECORDING_DURATION (1500ms) 匹配
        self.animation.setDuration(1500)
        # InOutCubic 模拟眼球的自然加速减速 (Smooth Pursuit)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.hide()

    def paintEvent(self, event):
        """绘制全屏半透明黑色遮罩"""
        painter = QPainter(self)
        # 黑色，透明度 220 (0-255)，约 86% 不透明度
        painter.setBrush(QColor(0, 0, 0, 220))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

    def show_overlay(self):
        """显示全屏遮罩"""
        self.showFullScreen()
        self.raise_()  # 确保覆盖在所有窗口之上
        self.setFocus()  # 获取焦点，防止用户误触其他地方

    def hide_overlay(self):
        self.hide()
        self.stimulus_dot.hide()

    @pyqtSlot(AcquisitionState, object)
    def update_display(self, state, data):
        """响应控制器状态更新"""
        self.stimulus_dot.hide()
        self.instruction_label.setText("")
        self.sub_label.setText("")

        if state == AcquisitionState.INSTRUCT:
            self.instruction_label.setText(str(data))

        elif state == AcquisitionState.COUNTDOWN:
            # 显示巨大的倒计时数字
            self.instruction_label.setStyleSheet("color: #00E676; font-size: 120px; font-weight: bold;")
            self.instruction_label.setText(str(data))
            self.sub_label.setText("Get Ready")

        elif state == AcquisitionState.RECORDING:
            # 恢复字体大小
            self.instruction_label.setStyleSheet("color: white; font-size: 64px; font-weight: bold;")

            action_str = str(data)
            display_text = action_str.replace('_', ' ').title()

            if 'BLINK' in action_str:
                self.instruction_label.setText(display_text)
                self.sub_label.setText("Keep head steady")
            else:
                # 眼动引导：文字显示在副标签，主视觉留给小球
                self.sub_label.setText(f"Look {display_text}")
                self._start_stimulus_animation(action_str)

        elif state == AcquisitionState.REST:
            self.instruction_label.setStyleSheet("color: #90CAF9; font-size: 64px; font-weight: bold;")
            self.instruction_label.setText(str(data))
            self.sub_label.setText("Relax your eyes")

    def _start_stimulus_animation(self, action):
        """根据动作方向计算轨迹并启动动画"""
        if action not in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
            return

        # 获取屏幕尺寸
        w, h = self.width(), self.height()

        # 计算中心位置 (修正：需要减去小球半径的一半才能真正居中)
        center_x = (w - self.dot_size) // 2
        center_y = (h - self.dot_size) // 2
        center_pos = QPoint(center_x, center_y)

        # 将小球重置到中心
        self.stimulus_dot.move(center_pos)
        self.stimulus_dot.show()

        # 计算目标位置 (使用百分比，适应不同分辨率)
        # 留出 15% 的边距，防止看太边上不舒服
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)

        target_pos = center_pos  # 默认不动

        if action == 'UP':
            target_pos = QPoint(center_x, margin_y)
        elif action == 'DOWN':
            target_pos = QPoint(center_x, h - margin_y - self.dot_size)
        elif action == 'LEFT':
            target_pos = QPoint(margin_x, center_y)
        elif action == 'RIGHT':
            target_pos = QPoint(w - margin_x - self.dot_size, center_y)

        # 设置动画参数
        self.animation.setStartValue(center_pos)
        self.animation.setEndValue(target_pos)
        self.animation.start()