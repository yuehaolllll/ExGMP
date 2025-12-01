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

        # --- 1. 获取后端参数 ---
        if self.data_processor:
            self.num_channels = self.data_processor.num_channels
            self.sample_rate = self.data_processor.sampling_rate
            self.downsample_factor = self.data_processor.downsample_factor
        else:
            self.num_channels = 8
            self.sample_rate = 1000
            self.downsample_factor = 1

        self.is_review_mode = False
        self.plot_seconds = 5

        # 预分配 X 轴缓存
        self._x_axis_cache = None
        self._precompute_x_axis()

        # 状态
        self.individual_scales = []
        self.plot_items = []
        self.plot_curves = []
        self.marker_lines = []
        self.temp_marker_lines = []
        self._is_reconfiguring = False
        self._initial_autorange_done = False

        # --- 2. 独立的底部时间轴 (Footer) ---
        # 这是一个专门用来显示 X 轴刻度的 PlotItem，不画波形
        # 它的存在是为了让上面的数据通道能够完美平分高度
        self.footer_plot = pg.PlotItem()
        self.footer_plot.getViewBox().setBorder(None)

        # 配置 Footer 的左轴：必须与上方通道完全一致，才能对齐！
        self.footer_plot.showAxis('left', True)
        self.footer_plot.getAxis('left').setWidth(60)  # 锁定宽度 60
        self.footer_plot.getAxis('left').setPen(None)  # 隐藏线条
        self.footer_plot.getAxis('left').setStyle(showValues=False)  # 隐藏文字

        # 配置 Footer 的右轴：同样为了对齐
        self.footer_plot.showAxis('right', True)
        self.footer_plot.getAxis('right').setWidth(10)  # 锁定宽度 10
        self.footer_plot.getAxis('right').setPen(None)
        self.footer_plot.getAxis('right').setStyle(showValues=False)

        # 配置 Footer 的底轴：显示时间
        self.footer_plot.setLabel('bottom', 'Time', units='s')
        self.footer_plot.showAxis('bottom', True)
        # 设置轴线颜色为灰色
        axis_pen = pg.mkPen(color='#808080', width=1)
        self.footer_plot.getAxis('bottom').setPen(axis_pen)

        # 固定高度：只给它留出显示文字的高度
        self.footer_plot.setMaximumHeight(40)

        # --- 3. 定时器 ---
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(16)  # ~60 FPS
        self.plot_update_timer.timeout.connect(self.update_display)

        # --- 4. UI 构建 ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.graphics_layout = pg.GraphicsLayoutWidget()
        # 紧凑布局，减少缝隙 (设为 0 是无缝的关键)
        self.graphics_layout.ci.layout.setSpacing(0)
        main_layout.addWidget(self.graphics_layout)

        # 初始化
        self.reconfigure_channels(self.num_channels)

    # --- 预计算 X 轴 ---
    def _precompute_x_axis(self):
        effective_rate = self.sample_rate / self.downsample_factor
        max_duration = 10.0
        num_points = int(effective_rate * max_duration)
        self._x_axis_cache = np.linspace(0, max_duration, num_points, dtype=np.float32)

    # --- 生命周期 ---
    def start_updates(self):
        if not self.plot_update_timer.isActive():
            self.plot_update_timer.start()

    def stop_updates(self):
        if self.plot_update_timer.isActive():
            self.plot_update_timer.stop()

    @pyqtSlot(int)
    def reconfigure_channels(self, num_channels):
        if self.num_channels == num_channels and len(self.plot_items) == num_channels:
            return

        self._is_reconfiguring = True
        self.plot_update_timer.stop()

        self.num_channels = num_channels
        self.individual_scales = [200.0] * num_channels

        self.graphics_layout.clear()
        self.plot_items.clear()
        self.plot_curves.clear()

        # 定义统一的坐标轴画笔颜色
        #axis_pen = pg.mkPen(color='#808080', width=1)
        border_pen = pg.mkPen(color='#000000', width=1)

        # 重新创建绘图对象
        for i in range(self.num_channels):
            p = pg.PlotItem()

            # --- 样式核心修改 ---
            # 1. 去除 ViewBox 内边框，消除“盒子感”
            p.getViewBox().setBorder(None)

            # 2. 开启四周坐标轴以形成轮廓
            p.showAxis('right', True)
            p.showAxis('left', True)
            p.showAxis('bottom', True)


            p.showAxis('top', True)
            p.getAxis('top').setPen(border_pen)
            p.getAxis('top').setStyle(showValues=False)  # 只画线，不显字


            # 3. 设置坐标轴颜色
            p.getAxis('left').setPen(border_pen)
            p.getAxis('bottom').setPen(border_pen)
            p.getAxis('right').setPen(border_pen)

            # 4. 锁定左右坐标轴宽度，确保所有通道波形区严格对齐
            p.getAxis('left').setWidth(60)  # 左侧留给刻度值
            p.getAxis('right').setWidth(10)  # 右侧封口

            # 5. 隐藏不需要的数值
            # 右侧：只显示线
            p.getAxis('right').setStyle(showValues=False)
            # 底部：所有数据通道都不显示数字（由 Footer 统一显示）
            p.getAxis('bottom').setStyle(showValues=False)

            # 性能优化配置
            p.setDownsampling(auto=True, mode='peak')
            p.setClipToView(True)

            # 网格设置
            p.showGrid(x=True, y=True, alpha=0.3)

            p.setYRange(-self.individual_scales[i], self.individual_scales[i])

            # 交互配置
            p.getViewBox().setMouseEnabled(x=True, y=True)
            p.getViewBox().sigYRangeChanged.connect(partial(self._on_y_range_changed, i))

            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = p.plot(pen=pg.mkPen(color=color, width=2))

            self.plot_items.append(p)
            self.plot_curves.append(curve)

        # 更新布局
        self._update_layout()

        self._initial_autorange_done = False
        self._is_reconfiguring = False
        self.plot_update_timer.start()

    def _update_layout(self):
        """排版逻辑：数据通道平分高度，底部放置独立时间轴"""
        gl = self.graphics_layout.ci
        layout = gl.layout
        gl.clear()  # 清空 Item 引用

        # 重置行高权重
        for r in range(layout.rowCount()):
            layout.setRowStretchFactor(r, 0)
            layout.setRowPreferredHeight(r, 0)
            layout.setRowMinimumHeight(r, 0)

        visible_items = [(i, p) for i, p in enumerate(self.plot_items) if p.isVisible()]

        # 如果没有可见通道，直接结束
        if not visible_items:
            return

        # 找到第一个可见的图表作为 X 轴联动的 Master
        master_plot = visible_items[0][1]

        # --- 1. 循环添加数据通道 ---
        for row, (idx, plot) in enumerate(visible_items):
            # X 轴联动
            if row == 0:
                plot.setXLink(None)
            else:
                plot.setXLink(master_plot)

            plot.setYLink(None)

            # 设置左侧标签
            color = PLOT_COLORS[idx % len(PLOT_COLORS)]
            plot.setLabel('left', f"CH {idx + 1}", units='µV', color=color)

            # 清空底部 Label (因为数字和单位都由 Footer 负责)
            plot.setLabel('bottom', None)

            # 将 Item 添加到布局
            gl.addItem(plot, row=row, col=0)

            # --- 关键布局设置 ---
            # 1. 消除缝隙
            layout.setRowSpacing(row, 0)
            # 2. 强制均分高度：所有通道权重均为 1
            layout.setRowStretchFactor(row, 1)
            # 3. 忽略内容高度对布局的影响
            layout.setRowPreferredHeight(row, 0)
            layout.setRowMinimumHeight(row, 0)

        # --- 2. 添加独立的 Footer 时间轴 ---
        footer_row = len(visible_items)

        # Footer 必须联动 X 轴，这样拖动波形时时间轴才会动
        self.footer_plot.setXLink(master_plot)

        gl.addItem(self.footer_plot, row=footer_row, col=0)

        # Footer 布局设置
        layout.setRowSpacing(footer_row, 0)
        layout.setRowStretchFactor(footer_row, 0)  # 权重为 0，不参与平分
        layout.setRowPreferredHeight(footer_row, 40)  # 固定高度
        layout.setRowMinimumHeight(footer_row, 40)

    # --- 核心绘制循环 (High Performance) ---
    def update_display(self):
        if not self.isVisible() or self.is_review_mode or self._is_reconfiguring or not self.data_processor:
            return

        full_data = self.data_processor.get_plot_data()
        if full_data is None:
            return

        effective_rate = self.sample_rate / self.downsample_factor
        points_to_show = int(self.plot_seconds * effective_rate)

        current_samples = full_data.shape[1]

        if current_samples >= points_to_show:
            y_data_slice = full_data[:, -points_to_show:]
            x_data = self._x_axis_cache[:points_to_show]
        else:
            y_data_slice = full_data
            x_data = self._x_axis_cache[:current_samples]

        for curve, y_row in zip(self.plot_curves, y_data_slice):
            if curve.isVisible():
                curve.setData(x_data, y_row, skipFiniteCheck=True)

        if not self._initial_autorange_done and current_samples > 10:
            for p in self.plot_items:
                p.enableAutoRange(axis='y', enable=False)
            self._initial_autorange_done = True

    # --- 交互槽函数 ---
    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sample_rate == new_rate: return
        self.sample_rate = new_rate
        self._precompute_x_axis()
        for p in self.plot_items:
            p.setXRange(0, self.plot_seconds)

    @pyqtSlot(int)
    def set_plot_duration(self, seconds):
        if self.is_review_mode or seconds == self.plot_seconds: return
        self.plot_seconds = seconds
        for p in self.plot_items:
            p.setXRange(0, self.plot_seconds)

        effective_rate = self.sample_rate / self.downsample_factor
        if len(self._x_axis_cache) < int(seconds * effective_rate):
            self._precompute_x_axis()

    def toggle_visibility(self, channel, visible):
        if 0 <= channel < len(self.plot_items):
            self.plot_items[channel].setVisible(visible)
            self._update_layout()

    def _on_y_range_changed(self, channel_index):
        if self._is_reconfiguring: return
        plot = self.plot_items[channel_index]
        if plot.getAxis('left').scene():
            view_range = plot.getViewBox().viewRange()[1]
            scale = (view_range[1] - view_range[0]) / 2
            self.individual_scales[channel_index] = scale

    @pyqtSlot(int, float)
    def adjust_scale(self, channel, new_scale):
        if 0 <= channel < len(self.plot_items):
            self.individual_scales[channel] = new_scale
            self.plot_items[channel].setYRange(-new_scale, new_scale)

    @pyqtSlot(int, str)
    def update_channel_name(self, channel, new_name):
        if 0 <= channel < len(self.plot_items):
            self.plot_items[channel].getAxis('left').setLabel(new_name, units='µV')

    @pyqtSlot(int)
    def set_vertical_scale(self, scale_uv):
        """
        设置 Y 轴缩放
        :param scale_uv: 0 为 Auto, 其他值为 +/- uV 限制
        """
        # 更新所有通道的 scale
        for i, p in enumerate(self.plot_items):
            if scale_uv == 0:
                # 开启自动缩放
                p.enableAutoRange(axis='y', enable=True)
            else:
                # 关闭自动缩放并设置固定范围
                p.enableAutoRange(axis='y', enable=False)
                p.setYRange(-scale_uv, scale_uv)

                # 如果需要更新内部状态
                if i < len(self.individual_scales):
                    self.individual_scales[i] = float(scale_uv)

    # --- Marker 和 Static Mode ---
    @pyqtSlot()
    def show_live_marker(self):
        pos = self.plot_seconds
        pen = pg.mkPen('g', style=Qt.PenStyle.DashLine, width=2)
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

    def display_static_data(self, data, sampling_rate, markers=None, channel_names=None):
        self.is_review_mode = True
        self.stop_updates()

        num_channels, num_samples = data.shape
        self.reconfigure_channels(num_channels)
        self.clear_plots(for_static=True)

        duration = num_samples / sampling_rate
        time_vector = np.linspace(0, duration, num_samples, dtype=np.float32)

        max_val = np.max(np.abs(data)) if np.any(data) else 50.0
        if max_val < 10: max_val = 50.0

        for i, p in enumerate(self.plot_items):
            p.setXRange(0, duration)
            p.setYRange(-max_val, max_val)
            self.plot_curves[i].setData(time_vector, data[i], skipFiniteCheck=True)

        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)

        if markers and 'timestamps' in markers:
            self._draw_static_markers(markers, sampling_rate)

    def _draw_static_markers(self, markers, fs):
        timestamps, labels = markers['timestamps'], markers['labels']
        pen = pg.mkPen('r', style=Qt.PenStyle.DashLine, width=1)
        for ts, lbl in zip(timestamps, labels):
            t_sec = float(ts) / fs
            for p in self.plot_items:
                line = pg.InfiniteLine(pos=t_sec, angle=90, pen=pen, label=str(lbl),
                                       labelOpts={'position': 0.1, 'color': 'r', 'movable': True})
                p.addItem(line)
                self.marker_lines.append(line)

    def clear_plots(self, for_static=False):
        for line in self.marker_lines:
            if line.scene(): line.scene().removeItem(line)
        self.marker_lines.clear()

        if not for_static:
            self.is_review_mode = False
            self._initial_autorange_done = False
            empty = np.array([], dtype=np.float32)
            for c in self.plot_curves: c.setData(empty, empty)
            for p in self.plot_items: p.enableAutoRange(axis='y', enable=True)