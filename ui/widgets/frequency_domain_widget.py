# File: ui/widgets/frequency_domain_widget.py

import pyqtgraph as pg
from PyQt6.QtCore import pyqtSlot
import numpy as np

PLOT_COLORS = [
    "#007BFF", "#28A745", "#DC3545", "#17A2B8",
    "#FD7E14", "#6F42C1", "#343A40", "#E83E8C", "#6610f2", "#20c997"
]


class FrequencyDomainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_channels = 8
        self.curves = []

        self.ci.layout.setContentsMargins(5, 5, 5, 5)

        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', "Frequency", units='Hz')
        self.plot.setLabel('left', "Magnitude", units='µV')
        self.plot.setTitle("Frequency Domain (FFT)")
        self.plot.setLogMode(x=False, y=False)
        self.plot.setXRange(0, 80)  # 关注 0-80Hz

        # 优化显示
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setDownsampling(auto=True, mode='peak')
        self.plot.setClipToView(True)
        self.plot.setMenuEnabled(False)
        self.plot.getViewBox().setBorder(pg.mkPen(color='#B0B0B0', width=1))

        self.legend = self.plot.addLegend(offset=(10, 10))
        self.legend.setBrush(pg.mkBrush(color=(255, 255, 255, 150)))

        self.reconfigure_channels(self.num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        if self.num_channels == num_channels and len(self.curves) == num_channels:
            return

        self.num_channels = num_channels
        self.plot.clear()
        self.curves.clear()
        if self.legend.scene(): self.legend.clear()

        for i in range(self.num_channels):
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = self.plot.plot(pen=pg.mkPen(color=color, width=1.5), name=f"CH {i + 1}")
            self.curves.append(curve)

    @pyqtSlot(np.ndarray, np.ndarray)
    def update_realtime_fft(self, freqs: np.ndarray, mags: np.ndarray, force=False):
        """
        接收 FFT 数据并绘制。
        freqs, mags 都是 float32。
        """
        # 1. 性能阻断：如果不可见，完全不处理
        if not self.isVisible() and not force:
            return

        # 2. 维度检查
        if mags.shape[0] != len(self.curves):
            if mags.shape[0] == self.num_channels:
                self.reconfigure_channels(self.num_channels)
            else:
                return

        # 3. 去除直流分量 (Index 0)
        # 即使后端没有去，前端显示时切掉第一个点可以让图表纵坐标更合理
        if len(freqs) > 1:
            f_data = freqs[1:]
            m_data = mags[:, 1:]
        else:
            return

        # 4. 批量更新
        for curve, mag_row in zip(self.curves, m_data):
            if curve.isVisible():
                curve.setData(f_data, mag_row, skipFiniteCheck=True)

    def display_static_fft(self, freqs, mags, channel_names):
        if mags.shape[0] != self.num_channels:
            self.reconfigure_channels(mags.shape[0])

        if channel_names:
            for i, name in enumerate(channel_names):
                if i < len(self.curves):
                    self.curves[i].opts['name'] = name
            # 重建图例以显示新名字
            self.legend.clear()
            for c in self.curves: self.legend.addItem(c, c.opts['name'])

        self.update_realtime_fft(freqs, mags, force=True)  # 复用逻辑
        self.plot.autoRange()

    @pyqtSlot(int, str)
    def update_channel_name(self, channel: int, new_name: str):
        """更新图例名称"""
        if 0 <= channel < len(self.curves):
            # 1. 更新曲线对象的内部名称
            self.curves[channel].opts['name'] = new_name

            # 2. PyQtGraph 的 Legend 更新比较繁琐，最稳健的方法是重建图例
            # 这种操作不是高频的，所以重建是可以接受的
            self.legend.clear()
            for curve in self.curves:
                self.legend.addItem(curve, curve.opts['name'])

    def clear_plots(self):
        empty = np.array([], dtype=np.float32)
        for curve in self.curves:
            curve.setData(empty, empty)