# File: ui/widgets/header_bar.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSlot, QSize
import time


class HeaderStatusWidget(QWidget):
    """
    显示在菜单栏右上角的 状态、数据率信息。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 背景透明
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        # 【优化1】调整边距：增加上下边距(2px)，防止文字贴顶被切断
        layout.setContentsMargins(15, 2, 15, 2)
        layout.setSpacing(15)

        # 【优化2】核心修复：强制整个布局垂直居中
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.last_stat_time = time.time()

        # --- 状态标签 ---
        self.status_lbl = QLabel("Status: Disconnected")
        self.pps_lbl = QLabel("PPS: 0.0")
        self.kbs_lbl = QLabel("Rate: 0.0 KB/s")

        # 【优化3】设置标签内部文字垂直居中，防止字体自身基线偏移
        for lbl in [self.status_lbl, self.pps_lbl, self.kbs_lbl]:
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # 字体样式
        status_style = "font-size: 9pt; color: #555;"
        self.status_lbl.setStyleSheet(status_style)
        self.pps_lbl.setStyleSheet(status_style)
        self.kbs_lbl.setStyleSheet(status_style)

        # --- 布局排列 ---
        layout.addWidget(self.status_lbl)

        # 添加分割线
        layout.addWidget(self._create_separator())
        layout.addWidget(self.pps_lbl)

        # 添加分割线
        layout.addWidget(self._create_separator())
        layout.addWidget(self.kbs_lbl)

    def _create_separator(self):
        """创建垂直分割线，并固定高度以防撑乱布局"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #CCC;")

        # 【优化4】固定分割线高度，使其看起来像个小竖条，而不是撑满全高
        line.setFixedHeight(14)

        return line

    @pyqtSlot(str)
    def update_status_message(self, message):
        self.status_lbl.setText(f"Status: {message}")

        # 根据状态改变颜色
        if "Connected" in message or "已连接" in message:
            # 绿色, 加粗
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #2E7D32; font-weight: bold;")
        elif "Disconnected" in message:
            # 灰色
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #555;")
            # 断开时清零数据
            self.pps_lbl.setText("PPS: 0.0")
            self.kbs_lbl.setText("Rate: 0.0 KB/s")
            self.last_stat_time = time.time()
        else:
            # 红色 (错误)
            self.status_lbl.setStyleSheet("font-size: 9pt; color: #C62828;")

    @pyqtSlot(int, int)
    def update_stats(self, packet_count, byte_count):
        """更新 PPS 和 KB/s"""
        current_time = time.time()
        elapsed = current_time - self.last_stat_time

        # 限制刷新频率，避免闪烁
        if elapsed > 0.5:
            pps = packet_count / elapsed
            kbs = (byte_count / elapsed) / 1024

            self.pps_lbl.setText(f"PPS: {pps:.1f}")
            self.kbs_lbl.setText(f"Rate: {kbs:.1f} KB/s")

            self.last_stat_time = current_time

    def sizeHint(self):
        """建议尺寸，确保在某些系统下能获得足够的高度"""
        return QSize(400, 30)