from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMovie


class SplashWidget(QWidget):
    """
    一个用于显示启动动画的QWidget，将被放入主窗口的QStackedWidget中。
    """

    def __init__(self, animation_path, parent=None):
        super().__init__(parent)

        # 使用垂直布局，并设置居中对齐
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.animation_label = QLabel()
        self.movie = QMovie(animation_path)
        self.animation_label.setMovie(self.movie)

        layout.addWidget(self.animation_label)

    def start_animation(self):
        """开始播放动画"""
        self.movie.start()

    def stop_animation(self):
        """停止播放动画"""
        self.movie.stop()