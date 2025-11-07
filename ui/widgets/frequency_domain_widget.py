# In ui/widgets/frequency_domain_widget.py
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSlot
import numpy as np


PLOT_COLORS = [
    "#007BFF", "#28A745", "#DC3545", "#17A2B8",
    "#FD7E14", "#6F42C1", "#343A40", "#E83E8C"
]

class FrequencyDomainWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_channels = 8
        self.curves = []
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', "Frequency", units='Hz')
        self.plot.setLabel('left', "Magnitude", units='µV')
        self.plot.setLogMode(x=False, y=False)
        self.plot.setXRange(0, 300) # 只显示 0 到 120 Hz
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        self.reconfigure_channels(self.num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        """
        核心槽函数：清空并根据新的通道数重建FFT曲线和图例。
        """
        if self.num_channels == num_channels and self.curves:
            return

        print(f"FrequencyDomainWidget: Reconfiguring UI for {num_channels} channels.")
        self.num_channels = num_channels

        # --- 1. 清理旧的UI组件 ---
        self.clear_plots()  # 调用清理函数
        self.curves = []

        # 如果已存在图例，则从绘图中移除它
        if self.plot.legend:
            self.plot.legend.scene().removeItem(self.plot.legend)
            self.plot.legend = None

        # --- 2. 重新创建曲线 ---
        for i in range(self.num_channels):
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = self.plot.plot(
                pen=pg.mkPen(color=color, width=1.5),
                name=f"CH {i + 1}"  # name 参数用于图例
            )
            self.curves.append(curve)

        # --- 3. 重新创建并添加图例 ---
        # 只有在创建完所有曲线后才能添加图例，这样它才能自动填充
        self.plot.addLegend()

    @pyqtSlot(np.ndarray, np.ndarray)
    def update_realtime_fft(self, freqs: np.ndarray, mags: np.ndarray):
        """
        这个槽函数专门用于连接 DataProcessor 的 fft_data_ready 信号。
        它的签名与信号完全匹配。
        """
        # 调用我们通用的绘图方法
        self.plot_fft_data(freqs, mags)

    # >>> 将绘图逻辑提取到一个通用方法中 <<<
    def plot_fft_data(self, freqs: np.ndarray, mags: np.ndarray):
        """通用的绘图逻辑，负责将数据绘制到曲线上。"""
        if mags.shape[0] != self.num_channels:
            # 这个检查保持不变
            return

        for i in range(self.num_channels):
            if i < len(self.curves):
                # 忽略直流分量的逻辑也保持不变
                self.curves[i].setData(freqs[1:], mags[i, 1:])

        # 强制Y轴自动缩放的逻辑也保持不变
        self.plot.enableAutoRange(axis='y', enable=True)

    # >>> 保留一个给 ReviewDialog 使用的普通方法 <<<
    def display_static_fft(self, freqs: np.ndarray, mags: np.ndarray, channel_names: list):
        """
        这个方法专门给 ReviewDialog 调用，用于显示静态文件数据。
        """
        # 确保UI与文件数据的通道数匹配
        if mags.shape[0] != self.num_channels:
            self.reconfigure_channels(mags.shape[0])

        # 调用通用绘图方法
        self.plot_fft_data(freqs, mags)

        # 更新通道名称
        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)


    @pyqtSlot(int, str)
    def update_channel_name(self, channel: int, new_name: str):
        """专门用于更新图例中单个通道名称的槽函数。"""
        if self.plot.legend and 0 <= channel < len(self.curves):
            try:
                label_item = self.plot.legend.items[channel][1]
                label_item.setText(new_name)
            except IndexError:
                pass

    def clear_plots(self):
        """从绘图中移除所有曲线"""
        for curve in self.curves:
            self.plot.removeItem(curve)
        # 清空曲线列表的引用
        self.curves.clear()