# File: ui/widgets/band_power_widget.py

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import pyqtSlot

BAND_COLORS = {
    'Delta': "#007BFF",  # 蓝色
    'Theta': "#28A745",  # 绿色
    'Alpha': "#FD7E14",  # 橙色
    'Beta': "#DC3545",  # 红色
    'Gamma': "#6F42C1"  # 紫色
}

# 定义标准的脑电波段
BANDS = {
    'Delta': [0.5, 4],
    'Theta': [4, 8],
    'Alpha': [8, 13],
    'Beta': [13, 30],
    'Gamma': [30, 100]
}
BAND_NAMES = list(BANDS.keys())


class BandPowerWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. 基础布局设置
        self.ci.layout.setContentsMargins(10, 10, 10, 10)

        # 2. 添加 PlotItem
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('left', "Power Spectral Density", units='μV²/Hz')
        self.plot.setLabel('bottom', "")  # 底部文字由刻度代替
        self.plot.setTitle("Band Power Distribution")  # 增加标题

        # 3. 样式与性能设置
        self.plot.setLogMode(x=False, y=False)
        self.plot.showGrid(x=False, y=True, alpha=0.3)
        self.plot.setMenuEnabled(False)  # 禁用右键菜单
        self.plot.setClipToView(True)  # 裁剪视野外内容

        # 4. 交互限制 (关键)
        # 柱状图的 X 轴是固定的分类，严禁缩放和平移，否则柱子会跑丢
        self.plot.setMouseEnabled(x=False, y=True)

        # 锁定 X 轴范围，留出一点左右边距 (-0.5 到 4.5)
        self.plot.setXRange(-0.6, len(BAND_NAMES) - 0.4, padding=0)

        # 5. 视觉优化：添加与时域图一致的边框
        self.plot.getViewBox().setBorder(pg.mkPen(color='#B0B0B0', width=1))

        # 准备颜色和画笔
        brushes = [BAND_COLORS[name] for name in BAND_NAMES]
        # 给柱子加一个淡淡的轮廓线，视觉上更锐利
        pens = [pg.mkPen(color='#FFFFFF', width=1)] * len(BAND_NAMES)

        # 6. 创建条形图
        self.bar_graph = pg.BarGraphItem(
            x=np.arange(len(BAND_NAMES)),
            height=np.zeros(len(BAND_NAMES)),
            width=0.6,
            brushes=brushes,
            # pens=pens  # 如果觉得轮廓线不好看可以注释掉
        )
        self.plot.addItem(self.bar_graph)

        # 7. 设置X轴刻度 (文字替换数字)
        ticks = [list(enumerate(BAND_NAMES))]
        ax = self.plot.getAxis('bottom')
        ax.setTicks(ticks)
        ax.setStyle(tickTextOffset=8)  # 文字稍微下移一点

        # 启用 Y 轴自动缩放
        self.plot.enableAutoRange(axis='y', enable=True)
        # 设置最小 Y 范围，防止全 0 时坐标轴乱跳
        self.plot.setLimits(yMin=0)

    @pyqtSlot(np.ndarray)
    def update_plot(self, band_powers):
        """接收并更新条形图的高度"""

        # --- 优化 1: 性能阻断 ---
        # 窗口最小化或不可见时，坚决不重绘
        if not self.isVisible():
            return

        # --- 优化 2: 数据安全 ---
        if band_powers is None or len(band_powers) != len(BAND_NAMES):
            return

        # --- 优化 3: 数据清洗 (关键) ---
        # 防止传入 NaN (接触不良时) 或 Inf，这会导致绘图引擎崩溃或闪退
        # copy=False 尽可能原地操作
        safe_powers = np.nan_to_num(band_powers, posinf=0.0, neginf=0.0, copy=False)

        # 简单的阈值过滤，防止异常大的脉冲撑爆坐标轴（可选）
        # safe_powers = np.clip(safe_powers, 0, 10000)

        # 更新数据
        self.bar_graph.setOpts(height=safe_powers)

    def clear_plots(self):
        """重置条形图"""
        self.bar_graph.setOpts(height=np.zeros(len(BAND_NAMES)))