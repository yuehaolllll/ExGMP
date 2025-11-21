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

        # 添加绘图区域
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', "Frequency", units='Hz')
        self.plot.setLabel('left', "Magnitude", units='µV')
        self.plot.setLogMode(x=False, y=False)

        # 限制 X 轴显示范围 (例如 0-120Hz 是脑电主要区域，300Hz 也行)
        self.plot.setXRange(0, 120)
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        # 性能优化：禁用鼠标右键菜单 (在大数据量下能减少一点开销)
        self.plot.setMenuEnabled(False)

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
        self.clear_plots()

        # 清理图例 (更稳健的写法)
        if self.plot.legend:
            self.plot.legend.scene().removeItem(self.plot.legend)
            self.plot.legend = None

        # --- 2. 重新创建并添加图例 ---
        # 先添加 Legend，再添加曲线，pyqtgraph 处理得更好
        self.plot.addLegend(offset=(10, 10))

        # --- 3. 重新创建曲线 ---
        for i in range(self.num_channels):
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = self.plot.plot(
                pen=pg.mkPen(color=color, width=1.5),
                name=f"CH {i + 1}"
            )
            self.curves.append(curve)

    @pyqtSlot(np.ndarray, np.ndarray)
    def update_realtime_fft(self, freqs: np.ndarray, mags: np.ndarray):
        """
        连接 DataProcessor 的 fft_data_ready 信号。
        """
        # --- 核心优化 1：不可见时不更新 ---
        # 如果 Widget 被隐藏（例如切换了 Tab），直接返回。
        # 这能节省大量 CPU，防止阻塞主线程。
        if not self.isVisible():
            return

        self.plot_fft_data(freqs, mags)

    def plot_fft_data(self, freqs: np.ndarray, mags: np.ndarray):
        """通用的绘图逻辑"""
        if mags.shape[0] != self.num_channels:
            return

        # 确保频率轴长度匹配 (有时候 fft freqs 可能比 mag 多/少 1 个点，视实现而定)
        # 这里假设传入的数据已经是匹配的，或者 DataProcessor 做了切片
        # 通常 freqs 长度等于 mags.shape[1]

        for i in range(self.num_channels):
            if i < len(self.curves):
                # 忽略直流分量 (index 0)，从 1 开始
                # 只有当曲线可见时才更新数据 (虽然 FFT 通常全显示，但这是一个好习惯)
                if self.curves[i].isVisible():
                    self.curves[i].setData(freqs[1:], mags[i, 1:])

        # --- 核心优化 2：移除循环内的强制 AutoRange ---
        # 原代码：self.plot.enableAutoRange(axis='y', enable=True)
        # 移除原因：
        # 1. 性能开销巨大。
        # 2. 导致用户无法手动缩放 Y 轴查看细节。
        # 3. 导致画面抖动。

        # 如果你确实希望一开始能自动缩放，可以在 __init__ 或 reconfigure 后调用一次即可。
        # 或者，PyQtGraph 默认就会处理得很好（用户可以双击左键复位）。

    def display_static_fft(self, freqs: np.ndarray, mags: np.ndarray, channel_names: list):
        """ ReviewDialog 使用的静态显示 """
        if mags.shape[0] != self.num_channels:
            self.reconfigure_channels(mags.shape[0])

        # 静态显示时，我们可能希望强制自动缩放一次，以便用户看清全貌
        self.plot_fft_data(freqs, mags)
        self.plot.autoRange()  # 静态显示时可以调用一次

        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)

    @pyqtSlot(int, str)
    def update_channel_name(self, channel: int, new_name: str):
        """更新图例名称"""
        # 这是一个比较 tricky 的操作，因为 pyqtgraph 的 legend 更新比较繁琐
        # 但你原来的 try-except 写法是可行的
        if self.plot.legend and 0 <= channel < len(self.curves):
            try:
                # PyQTGraph 的 legend items 存储方式可能因版本而异
                # 最稳健的方式通常是清空重建，但这里的 hack 也可以
                label_item = self.plot.legend.items[channel][1]
                label_item.setText(new_name)
            except IndexError:
                pass

    def clear_plots(self):
        """移除所有曲线"""
        for curve in self.curves:
            self.plot.removeItem(curve)
        self.curves.clear()