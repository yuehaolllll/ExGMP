# File: ui/widgets/band_power_widget.py

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import pyqtSlot

BAND_COLORS = {
    'Delta': "#007BFF", 'Theta': "#28A745", 'Alpha': "#FD7E14", 'Beta': "#DC3545", 'Gamma': "#6F42C1"
}
BAND_NAMES = list(BAND_COLORS.keys())


class BandPowerWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.ci.layout.setContentsMargins(10, 10, 10, 10)
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('left', "Power", units='μV²')
        self.plot.setTitle("Band Power")

        self.plot.showGrid(x=False, y=True, alpha=0.3)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=True)  # 锁定 X 轴
        self.plot.setXRange(-0.6, len(BAND_NAMES) - 0.4, padding=0)
        self.plot.getViewBox().setBorder(pg.mkPen(color='#B0B0B0', width=1))

        brushes = [BAND_COLORS[name] for name in BAND_NAMES]

        # 柱状图 Item
        self.bar_graph = pg.BarGraphItem(
            x=np.arange(len(BAND_NAMES)),
            height=np.zeros(len(BAND_NAMES), dtype=np.float32),
            width=0.6,
            brushes=brushes
        )
        self.plot.addItem(self.bar_graph)

        # X轴刻度
        ax = self.plot.getAxis('bottom')
        ax.setTicks([list(enumerate(BAND_NAMES))])

        self.plot.enableAutoRange(axis='y', enable=True)

    @pyqtSlot(np.ndarray)
    def update_plot(self, band_powers):
        # 1. 性能阻断
        if not self.isVisible():
            return

        if band_powers is None or len(band_powers) != len(BAND_NAMES):
            return

        # 2. 安全检查 (替换 NaN/Inf)
        # 虽然 backend 尽量保证了，但 UI 层做最后一道防线
        safe_powers = np.nan_to_num(band_powers, nan=0.0, posinf=0.0, neginf=0.0)

        # 3. 更新
        self.bar_graph.setOpts(height=safe_powers)

    def clear_plots(self):
        self.bar_graph.setOpts(height=np.zeros(len(BAND_NAMES), dtype=np.float32))