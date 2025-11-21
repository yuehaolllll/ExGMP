# In ui/widgets/band_power_widget.py
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

        # 添加 PlotItem
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('left', "Power", units='μV²/Hz')
        self.plot.setLabel('bottom', "Brainwave Bands")

        # 样式设置
        self.plot.setLogMode(x=False, y=False)
        self.plot.showGrid(x=False, y=True, alpha=0.3)  # X轴网格通常不需要

        # --- 优化 1: 交互限制 ---
        # 禁用 X 轴的鼠标缩放/平移，因为柱状图的 X 轴是固定的分类
        self.plot.setMouseEnabled(x=False, y=True)
        # 禁用右键菜单 (性能 + 防误触)
        self.plot.setMenuEnabled(False)

        brushes = [BAND_COLORS[name] for name in BAND_NAMES]

        # 创建条形图
        self.bar_graph = pg.BarGraphItem(
            x=np.arange(len(BAND_NAMES)),
            height=np.zeros(len(BAND_NAMES)),
            width=0.6,
            brushes=brushes
        )
        self.plot.addItem(self.bar_graph)

        # 设置X轴刻度
        ticks = [list(enumerate(BAND_NAMES))]
        self.plot.getAxis('bottom').setTicks(ticks)

        # 启用自动缩放 (初始化时)
        self.plot.enableAutoRange(axis='y', enable=True)

    @pyqtSlot(np.ndarray)
    def update_plot(self, band_powers):
        """接收并更新条形图的高度"""

        # --- 优化 2: 核心性能保护 ---
        # 如果控件不可见，直接返回，拒绝消耗主线程 CPU
        if not self.isVisible():
            return

        # --- 优化 3: 安全检查 ---
        if len(band_powers) != len(BAND_NAMES):
            return

        # 更新数据
        self.bar_graph.setOpts(height=band_powers)

    def clear_plots(self):
        """重置条形图"""
        self.bar_graph.setOpts(height=np.zeros(len(BAND_NAMES)))