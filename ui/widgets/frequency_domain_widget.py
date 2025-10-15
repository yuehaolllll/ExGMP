# In ui/widgets/frequency_domain_widget.py
import pyqtgraph as pg

NUM_CHANNELS = 8

PLOT_COLORS = [
    "#007BFF", "#28A745", "#DC3545", "#17A2B8",
    "#FD7E14", "#6F42C1", "#343A40", "#E83E8C"
]

class FrequencyDomainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', "Frequency", units='Hz')
        self.plot.setLabel('left', "Magnitude", units='µV')
        self.plot.setLogMode(x=False, y=False)
        self.plot.setXRange(0, 120) # 只显示 0 到 120 Hz
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        self.curves = []
        for i in range(NUM_CHANNELS):
            curve = self.plot.plot(
                pen=pg.mkPen(color=PLOT_COLORS[i], width=1.5),  # 可以适当加粗线条
                name=f"CH {i + 1}"
            )
            self.curves.append(curve)

        self.plot.addLegend()

    def update_fft(self, freqs, mags):
        for i in range(NUM_CHANNELS):
            self.curves[i].setData(freqs, mags[i])

    def clear_plots(self):
        for curve in self.curves:
            curve.clear()