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

        # --- 1. 初始化绘图区域 ---
        # 设置内容边距，避免文字被边缘切断
        self.ci.layout.setContentsMargins(5, 5, 5, 5)

        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', "Frequency", units='Hz')
        self.plot.setLabel('left', "Magnitude", units='µV')
        self.plot.setTitle("Frequency Domain (FFT)")  # 增加标题

        # 默认不使用 Log 模式 (线性刻度更适合观察特定的脑电频率峰值)
        self.plot.setLogMode(x=False, y=False)

        # --- 2. 性能与样式优化 ---
        # 限制 X 轴显示范围 (0-60Hz 或 0-100Hz 是最常用的脑电区域)
        self.plot.setXRange(0, 80)
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        # 性能设置
        self.plot.setDownsampling(auto=True, mode='peak')
        self.plot.setClipToView(True)
        self.plot.setMenuEnabled(False)  # 禁用右键菜单

        # 视觉统一：添加灰色边框
        self.plot.getViewBox().setBorder(pg.mkPen(color='#B0B0B0', width=1))

        # 初始化图例
        self.legend = self.plot.addLegend(offset=(10, 10))
        # 设置图例半透明背景
        self.legend.setBrush(pg.mkBrush(color=(255, 255, 255, 150)))

        self.reconfigure_channels(self.num_channels)

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        """
        核心槽函数：清空并根据新的通道数重建FFT曲线和图例。
        """
        # 即使通道数没变，为了保险（防止颜色或图例错乱），这里允许重建
        # 只要保证不频繁调用即可
        if self.num_channels == num_channels and len(self.curves) == num_channels:
            return

        print(f"FrequencyDomainWidget: Reconfiguring UI for {num_channels} channels.")
        self.num_channels = num_channels

        # --- 1. 清理旧资源 ---
        self.plot.clear()  # 这会移除所有 items (curves)
        self.curves.clear()

        # 重新添加图例 (clear() 可能不会移除 legend 对象，但会清空其内容)
        if self.legend.scene() is None:
            self.legend = self.plot.addLegend(offset=(10, 10))
        else:
            self.legend.clear()

        # --- 2. 重建曲线 ---
        for i in range(self.num_channels):
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            # 创建曲线
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
        # --- 核心优化 1：不可见阻断 ---
        # 节省 CPU，不可见时不进行任何绘图计算
        if not self.isVisible():
            return

        self.plot_fft_data(freqs, mags)

    def plot_fft_data(self, freqs: np.ndarray, mags: np.ndarray):
        """通用的绘图逻辑"""
        # 安全性检查
        if mags.shape[0] != len(self.curves):
            # 如果数据维度不匹配，尝试触发重构或直接返回
            if mags.shape[0] == self.num_channels:
                self.reconfigure_channels(self.num_channels)
            else:
                return

        # --- 核心优化 2：预处理与切片 ---
        # 1. 去除直流分量 (Index 0, 0Hz)
        # 直流分量通常巨大，会压缩有用信号的显示比例，必须去除
        # 放在循环外切片，减少开销
        if len(freqs) > 1:
            f_data = freqs[1:]
            m_data = mags[:, 1:]
        else:
            return  # 数据点太少

        # 2. 批量更新
        # 使用 zip 同时遍历曲线和数据，避免索引查找
        for curve, mag_row in zip(self.curves, m_data):
            if curve.isVisible():
                # --- 核心优化 3：skipFiniteCheck ---
                # 极大提升 setData 速度
                curve.setData(f_data, mag_row, skipFiniteCheck=True)

    def display_static_fft(self, freqs: np.ndarray, mags: np.ndarray, channel_names: list):
        """ ReviewDialog 使用的静态显示 """
        # 确保通道数匹配
        if mags.shape[0] != self.num_channels:
            self.reconfigure_channels(mags.shape[0])

        # 更新名称
        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)

        # 绘制
        self.plot_fft_data(freqs, mags)

        # 静态显示时，自动缩放一次以便看清全貌
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
        """清空数据但保留曲线对象（用于重置状态）"""
        empty = np.array([])
        for curve in self.curves:
            curve.setData(empty, empty)