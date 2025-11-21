# File: ui/widgets/header_bar.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSlot
import time


class HeaderStatusWidget(QWidget):
    """
    显示在菜单栏右上角的 状态、数据率信息。
    (去掉了 Logo 类和 窗口控制按钮)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 背景透明，完美融入菜单栏
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        # 调整边距：左边留20px防止紧贴菜单项，右边留10px防止紧贴窗口边缘
        layout.setContentsMargins(20, 0, 15, 0)
        layout.setSpacing(15)

        self.last_stat_time = time.time()

        # --- 状态标签 ---
        self.status_lbl = QLabel("Status: Disconnected")
        self.pps_lbl = QLabel("PPS: 0.0")
        self.kbs_lbl = QLabel("Rate: 0.0 KB/s")

        # 字体样式
        status_style = "font-size: 9pt; color: #555;"
        self.status_lbl.setStyleSheet(status_style)
        self.pps_lbl.setStyleSheet(status_style)
        self.kbs_lbl.setStyleSheet(status_style)

        # --- 布局排列 ---
        layout.addWidget(self.status_lbl)

        # 分隔竖线 1
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.VLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        line1.setStyleSheet("color: #CCC;")
        layout.addWidget(line1)

        layout.addWidget(self.pps_lbl)

        # 分隔竖线 2
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.VLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("color: #CCC;")
        layout.addWidget(line2)

        layout.addWidget(self.kbs_lbl)

    @pyqtSlot(str)
    def update_status_message(self, message):
        self.status_lbl.setText(f"Status: {message}")
        if "Connected" in message or "已连接" in message:
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #2E7D32; font-weight: bold;")  # 绿色
        elif "Disconnected" in message:
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #555;")  # 灰色
            self.pps_lbl.setText("PPS: 0.0")
            self.kbs_lbl.setText("Rate: 0.0 KB/s")
            self.last_stat_time = time.time()
        else:
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #C62828;")  # 红色

    @pyqtSlot(int, int)
    def update_stats(self, packet_count, byte_count):
        current_time = time.time()
        elapsed = current_time - self.last_stat_time
        if elapsed > 0.5:
            pps = packet_count / elapsed
            kbs = (byte_count / elapsed) / 1024
            self.pps_lbl.setText(f"PPS: {pps:.1f}")
            self.kbs_lbl.setText(f"Rate: {kbs:.1f} KB/s")
            self.last_stat_time = current_time