# File: ui/widgets/time_domain_widget.py

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import QTimer, pyqtSlot, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from functools import partial

PLOT_COLORS = [
    "#007BFF", "#28A745", "#DC3545", "#17A2B8", "#FD7E14",
    "#6F42C1", "#343A40", "#E83E8C", "#6610f2", "#20c997"
]


class TimeDomainWidget(QWidget):
    def __init__(self, data_processor=None, parent=None):
        super().__init__(parent)
        self.data_processor = data_processor

        # --- 1. 初始化状态变量 ---
        if self.data_processor:
            self.num_channels = self.data_processor.num_channels
            self.sample_rate = self.data_processor.sampling_rate
        else:
            self.num_channels = 8
            self.sample_rate = 1000

        self.is_review_mode = False
        self.static_data = None
        self.static_time_vector = None
        self.plot_seconds = 5

        # 缓存与标志位
        self._time_vector = None
        self.marker_lines = []
        self.temp_marker_lines = []
        self._initial_autorange_done = False
        self._is_reconfiguring = False

        # 绘图对象列表
        self.individual_scales = []
        self.plot_items = []  # 存储 pg.PlotItem
        self.plot_curves = []  # 存储 pg.PlotCurveItem

        # --- 2. 定时器 ---
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(33)  # ~30 FPS
        self.plot_update_timer.timeout.connect(self.update_display)

        # --- 3. 构建 UI ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 核心绘图容器
        self.graphics_layout = pg.GraphicsLayoutWidget()
        # 设置通道间的间距，露出背景形成分割线
        self.graphics_layout.ci.layout.setSpacing(10)

        main_layout.addWidget(self.graphics_layout)

        # --- 4. 初始化配置 ---
        self._recalc_time_vector()
        self.reconfigure_channels(self.num_channels)

    # --- 生命周期控制 ---
    def start_updates(self):
        if not self.plot_update_timer.isActive():
            self.plot_update_timer.start()

    def stop_updates(self):
        if self.plot_update_timer.isActive():
            self.plot_update_timer.stop()

    # --- 核心配置逻辑 ---
    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        """重建所有通道的绘图对象"""
        # 只有在通道数真正改变，或者初次初始化时才执行
        if self.num_channels == num_channels and len(self.plot_items) == num_channels:
            return

        self._is_reconfiguring = True
        print(f"TimeDomainWidget: Reconfiguring for {num_channels} channels.")

        self.num_channels = num_channels
        self.individual_scales = [200.0] * num_channels

        # 1. 清理现有资源
        self.graphics_layout.clear()  # 清空布局
        self.plot_items.clear()
        self.plot_curves.clear()

        # 2. 创建新的绘图对象
        for i in range(self.num_channels):
            # 创建 PlotItem
            p = pg.PlotItem()

            # --- 性能优化设置 ---
            p.setDownsampling(auto=True, mode='peak')
            p.setClipToView(True)
            # 只保留横向网格，去除竖向网格，保持底部通道风格一致
            p.showGrid(x=False, y=True, alpha=0.2)

            # 设置初始范围和交互
            p.setYRange(-self.individual_scales[i], self.individual_scales[i])
            # 开启 X 轴交互以支持缩放和联动
            p.getViewBox().setMouseEnabled(x=True, y=True)

            # --- 视觉优化：添加边框 ---
            p.getViewBox().setBorder(pg.mkPen(color='#B0B0B0', width=1))

            # 信号连接
            p.getViewBox().sigYRangeChanged.connect(partial(self._on_y_range_changed, i))

            # 创建曲线
            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = p.plot(pen=pg.mkPen(color=color, width=1.5))

            self.plot_items.append(p)
            self.plot_curves.append(curve)

        # 3. 布局排版
        self._update_layout()

        self._initial_autorange_done = False
        self._is_reconfiguring = False

    def _update_layout(self):
        """执行网格布局，应用 Stretch Factor 解决高度分配问题"""
        gl = self.graphics_layout.ci
        layout = gl.layout

        # 必须先清空 GraphicsLayout 内部的 Item 引用（虽然前面 clear 过，这里是防卫性编程）
        gl.clear()

        # 清除旧布局属性 (关键步骤，防止旧权重残留)
        for r in range(layout.rowCount()):
            layout.setRowStretchFactor(r, 0)
            layout.setRowPreferredHeight(r, 0)

        visible_items = [(i, p) for i, p in enumerate(self.plot_items) if p.isVisible()]
        total_visible = len(visible_items)

        master_plot = None  # 用于 X 轴联动的主图表

        for row, (idx, plot) in enumerate(visible_items):
            # 1. 设置 X 轴联动
            if row == 0:
                plot.setXLink(None)
                master_plot = plot
            elif master_plot:
                plot.setXLink(master_plot)

            plot.setYLink(None)  # Y轴独立

            # 2. 设置标签和轴显示
            color = PLOT_COLORS[idx % len(PLOT_COLORS)]
            plot.setLabel('left', f"CH {idx + 1}", units='µV', color=color)

            # 只有最后一行显示时间轴
            if row == total_visible - 1:
                plot.showAxis('bottom', True)
                plot.setLabel('bottom', 'Time', units='s')
                plot.getAxis('bottom').setStyle(showValues=True)
                plot.getAxis('bottom').setHeight(30)
            else:
                plot.showAxis('bottom', False)

            # 3. 添加到布局
            gl.addItem(plot, row=row, col=0)

            if row == total_visible - 1:
                # 最后一行：带有底部坐标轴 (约占 30px 高度)
                # 我们给它更大的拉伸权重 (12 vs 10)，让它在高度上获得补偿
                # 这样减去坐标轴高度后，剩余给波形的空间就和其他通道差不多了
                layout.setRowStretchFactor(row, 12)
            else:
                # 其他行：纯波形
                layout.setRowStretchFactor(row, 10)

                # 【重要】移除 setRowPreferredHeight
                # 移除硬性的高度约束，让布局管理器根据 StretchFactor 自由分配
                # layout.setRowPreferredHeight(row, 100) <--- 删除或注释掉这行

            layout.setRowMinimumHeight(row, 0)  # 允许压缩
            layout.setRowSpacing(row, 10)  # 保持行间距

    # --- 数据更新 (High Performance) ---
    def _recalc_time_vector(self):
        if self.data_processor:
            effective_rate = self.sample_rate / self.data_processor.downsample_factor
        else:
            effective_rate = self.sample_rate

        num_points = int(effective_rate * self.plot_seconds)
        self._time_vector = np.linspace(0, self.plot_seconds, num_points)

    def update_display(self):
        """实时刷新循环"""
        if self.is_review_mode or self._is_reconfiguring or not self.data_processor:
            return

        # Thread-safe getter
        full_data = self.data_processor.get_plot_data()
        if full_data is None or full_data.size == 0:
            return

        # 时间轴对齐
        target_len = len(self._time_vector)
        current_len = full_data.shape[1]

        if current_len >= target_len:
            display_data = full_data[:, -target_len:]
            t = self._time_vector
        else:
            effective_rate = self.sample_rate / self.data_processor.downsample_factor
            t = np.linspace(0, current_len / effective_rate, current_len)
            display_data = full_data

        # 绘图更新
        safe_channels = min(self.num_channels, display_data.shape[0])

        for i in range(safe_channels):
            # 仅更新可见通道，节省性能
            if self.plot_items[i].isVisible():
                # skipFiniteCheck=True 极大提升速度
                self.plot_curves[i].setData(t, display_data[i], skipFiniteCheck=True)

        if not self._initial_autorange_done and current_len > 10:
            self._disable_autorange()

    def _disable_autorange(self):
        for p in self.plot_items:
            p.enableAutoRange(axis='y', enable=False)
        self._initial_autorange_done = True

    # --- 交互与事件 ---
    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sample_rate == new_rate: return
        self.sample_rate = new_rate
        self.set_plot_duration(self.plot_seconds)

    @pyqtSlot(int)
    def set_plot_duration(self, seconds):
        if self.is_review_mode: return
        self.plot_seconds = seconds

        for p in self.plot_items:
            p.setXRange(0, self.plot_seconds)

        self._recalc_time_vector()

    def toggle_visibility(self, channel, visible):
        if 0 <= channel < len(self.plot_items):
            self.plot_items[channel].setVisible(visible)
            # 重新触发布局计算，以移除隐藏通道留下的空白
            self._update_layout()

    def _on_y_range_changed(self, channel_index):
        """用户手动缩放记录"""
        if self._is_reconfiguring: return
        if channel_index >= len(self.plot_items): return

        plot = self.plot_items[channel_index]
        if plot.getAxis('left').scene():
            y_range = plot.getViewBox().viewRange()[1]
            scale = (y_range[1] - y_range[0]) / 2
            self.individual_scales[channel_index] = scale if scale > 1e-9 else 1e-9

    @pyqtSlot(int, float)
    def adjust_scale(self, channel, new_scale):
        if 0 <= channel < len(self.plot_items):
            self.individual_scales[channel] = new_scale
            self.plot_items[channel].setYRange(-new_scale, new_scale)

    # --- 工具方法 ---
    @pyqtSlot(int, str)
    def update_channel_name(self, channel, new_name):
        if 0 <= channel < len(self.plot_items):
            self.plot_items[channel].getAxis('left').setLabel(new_name, units='µV')

    @pyqtSlot()
    def show_live_marker(self):
        pos = self.plot_seconds
        pen = pg.mkPen('g', style=pg.QtCore.Qt.PenStyle.DashLine, width=2)
        lines = []

        for p in self.plot_items:
            if p.isVisible():
                line = pg.InfiniteLine(pos=pos, angle=90, pen=pen)
                p.addItem(line)
                lines.append(line)

        self.temp_marker_lines.extend(lines)
        QTimer.singleShot(1500, partial(self._remove_temp_lines, lines))

    def _remove_temp_lines(self, lines):
        for line in lines:
            try:
                if line.scene(): line.scene().removeItem(line)
                if line in self.temp_marker_lines: self.temp_marker_lines.remove(line)
            except:
                pass

    # --- 回放模式 ---
    def display_static_data(self, data, sampling_rate, markers=None, channel_names=None):
        self.is_review_mode = True
        self.stop_updates()

        num_channels, num_samples = data.shape
        self.reconfigure_channels(num_channels)
        self.clear_plots(for_static=True)

        self.static_data = data
        duration = num_samples / sampling_rate
        self.static_time_vector = np.arange(num_samples) / sampling_rate

        # 自动缩放
        max_val = np.max(np.abs(data)) if np.any(data) else 50.0
        if max_val < 10: max_val = 50.0
        self.individual_scales = [max_val] * num_channels

        for i, p in enumerate(self.plot_items):
            p.setXRange(0, duration)
            p.setYRange(-max_val, max_val)
            # 重绘静态数据
            self.plot_curves[i].setData(self.static_time_vector, data[i], skipFiniteCheck=True)

        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)

        if markers and 'timestamps' in markers:
            self._draw_static_markers(markers, sampling_rate)

    def _draw_static_markers(self, markers, fs):
        timestamps, labels = markers['timestamps'], markers['labels']
        pen = pg.mkPen('r', style=pg.QtCore.Qt.PenStyle.DashLine, width=1)

        for ts, lbl in zip(timestamps, labels):
            t_sec = float(ts) / fs
            for p in self.plot_items:
                line = pg.InfiniteLine(pos=t_sec, angle=90, pen=pen, label=str(lbl),
                                       labelOpts={'position': 0.1, 'color': 'r', 'movable': True})
                p.addItem(line)
                self.marker_lines.append(line)

    def clear_plots(self, for_static=False):
        # 清理 Marker
        for line in self.marker_lines:
            if line.scene(): line.scene().removeItem(line)
        self.marker_lines.clear()

        if not for_static:
            self.is_review_mode = False
            self.static_data = None
            self._initial_autorange_done = False

            empty = np.array([])
            for c in self.plot_curves: c.setData(empty, empty)

            for p in self.plot_items: p.enableAutoRange(axis='y', enable=True)