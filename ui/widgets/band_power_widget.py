import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import pyqtSlot

BAND_COLORS = {
    'Delta': "#007BFF",  # 蓝色
    'Theta': "#28A745",  # 绿色
    'Alpha': "#FD7E14",  # 橙色
    'Beta':  "#DC3545",  # 红色
    'Gamma': "#6F42C1"   # 紫色
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
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('left', "Power", units='μV²/Hz')
        self.plot.setLabel('bottom', "Brainwave Bands")
        # 隐藏Y轴的对数刻度，因为能量值通常不大
        self.plot.setLogMode(x=False, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        brushes = [BAND_COLORS[name] for name in BAND_NAMES]

        # 创建一个条形图项目
        self.bar_graph = pg.BarGraphItem(
            x=np.arange(len(BAND_NAMES)),
            height=np.zeros(len(BAND_NAMES)),
            width=0.6,
            brushes=brushes # 使用主题中的蓝色
        )
        self.plot.addItem(self.bar_graph)

        # 设置X轴的刻度标签为波段名称，这是关键
        ticks = [list(enumerate(BAND_NAMES))]
        self.plot.getAxis('bottom').setTicks(ticks)
        # 禁用自动Y轴范围调整，以便我们手动控制
        self.plot.enableAutoRange(axis='y', enable=True)


    @pyqtSlot(np.ndarray)
    def update_plot(self, band_powers):
        """接收并更新条形图的高度"""
        self.bar_graph.setOpts(height=band_powers)

    def clear_plots(self):
        """重置条形图"""
        self.bar_graph.setOpts(height=np.zeros(len(BAND_NAMES)))