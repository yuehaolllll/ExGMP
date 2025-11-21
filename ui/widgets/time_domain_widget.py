# In ui/widgets/time_domain_widget.py
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import QTimer, pyqtSlot
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QStackedWidget
from enum import Enum
from functools import partial


# 绘图模式枚举
class PlotMode(Enum):
    INDIVIDUAL = 1
    STACKED = 2


PLOT_COLORS = [
    "#007BFF", "#28A745", "#DC3545", "#17A2B8", "#FD7E14",
    "#6F42C1", "#343A40", "#E83E8C", "#6610f2", "#20c997"
]

CHANNEL_HEIGHT = 1.0


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
        self.current_mode = PlotMode.STACKED
        self.plot_seconds = 5

        # 缓存时间轴，避免每帧重复计算
        self._time_vector = None

        self._is_updating_stacked_range = False
        self.marker_lines, self.temp_marker_lines = [], []
        self.stacked_view_scale = 200.0
        self._initial_autorange_done = False
        self._is_reconfiguring = False

        # 动态列表初始化
        self.individual_scales = []
        self.stacked_curves, self.stacked_labels = [], []
        self.individual_plots, self.individual_curves = [], []

        # --- 2. 定时器 ---
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.setInterval(33)  # ~30 FPS
        self.plot_update_timer.timeout.connect(self.update_display)

        # --- 3. 构建基础UI ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # 顶部按钮栏
        button_bar_layout = QHBoxLayout()
        self.switch_button = QPushButton("Switch to Individual View")
        self.switch_button.setFixedWidth(180)
        self.switch_button.clicked.connect(self._toggle_plot_mode)
        button_bar_layout.addStretch()
        button_bar_layout.addWidget(self.switch_button)
        main_layout.addLayout(button_bar_layout)

        # 绘图区域堆栈
        self.plot_stack = QStackedWidget()
        main_layout.addWidget(self.plot_stack)

        # --- 4. 初始化配置 ---
        self._recalc_time_vector()  # 预计算时间轴
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
        """根据新的通道数重建UI，清理旧资源"""
        # 如果通道数未变且UI已存在，跳过
        if self.num_channels == num_channels and self.plot_stack.count() > 0:
            return

        self._is_reconfiguring = True
        print(f"TimeDomainWidget: Reconfiguring UI for {num_channels} channels.")

        self.num_channels = num_channels
        self.individual_scales = [200.0] * num_channels

        # 1. 清理旧组件 (防止内存泄漏)
        while self.plot_stack.count() > 0:
            w = self.plot_stack.widget(0)
            self.plot_stack.removeWidget(w)
            w.deleteLater()

        # 2. 重建视图
        self.stacked_view = self._create_stacked_view()
        self.individual_view = self._create_individual_view()

        self.plot_stack.addWidget(self.stacked_view)
        self.plot_stack.addWidget(self.individual_view)

        # 3. 恢复状态
        self._update_individual_view_layout()
        self._set_plot_mode(self.current_mode)

        self._is_reconfiguring = False

    def _create_stacked_view(self):
        view = pg.GraphicsLayoutWidget()
        self.stacked_plot = view.addPlot(row=0, col=0)
        self.stacked_plot.setDownsampling(auto=True, mode='peak')  # 开启自动降采样提升性能
        self.stacked_plot.setClipToView(True)
        self.stacked_plot.setLabel('bottom', 'Time', units='s')
        self.stacked_plot.hideAxis('left')
        self.stacked_plot.showGrid(x=True, y=True, alpha=0.4)

        self.stacked_plot.getViewBox().setMouseEnabled(y=True)
        self.stacked_plot.getViewBox().sigYRangeChanged.connect(self._on_stacked_y_range_changed)

        self.stacked_curves, self.stacked_labels = [], []

        for i in range(self.num_channels):
            offset = (self.num_channels - 1 - i) * CHANNEL_HEIGHT
            color = PLOT_COLORS[i % len(PLOT_COLORS)]

            # 曲线
            curve = self.stacked_plot.plot(pen=pg.mkPen(color=color, width=1.5))
            self.stacked_curves.append(curve)

            # 标签
            label = pg.TextItem(f"CH {i + 1}", color=color, anchor=(0, 0.5))
            label.setPos(0, offset)  # 暂时设为0，update时会调整
            self.stacked_plot.addItem(label)
            self.stacked_labels.append(label)

        self._update_stacked_y_range()
        return view

    def _create_individual_view(self):
        view = pg.GraphicsLayoutWidget()
        view.ci.layout.setSpacing(2)
        self.individual_plots, self.individual_curves = [], []

        for i in range(self.num_channels):
            p = pg.PlotItem()
            p.setDownsampling(auto=True, mode='peak')
            p.setClipToView(True)
            p.showGrid(x=True, y=True, alpha=0.3)
            p.setYRange(-self.individual_scales[i], self.individual_scales[i])
            p.getViewBox().setMouseEnabled(x=True, y=True)
            p.getViewBox().sigYRangeChanged.connect(partial(self._on_individual_y_range_changed, i))

            color = PLOT_COLORS[i % len(PLOT_COLORS)]
            curve = p.plot(pen=pg.mkPen(color=color, width=1.5))

            self.individual_plots.append(p)
            self.individual_curves.append(curve)
        return view

    # --- 核心：数据更新与绘图 (高性能优化版) ---
    def _recalc_time_vector(self):
        """当采样率或时长改变时，预计算时间轴，避免每帧计算"""
        if self.data_processor:
            # 计算实际显示的点数（考虑降采样）
            effective_rate = self.sample_rate / self.data_processor.downsample_factor
        else:
            effective_rate = self.sample_rate

        num_points = int(effective_rate * self.plot_seconds)
        self._time_vector = np.linspace(0, self.plot_seconds, num_points)

    def update_display(self):
        """定时器回调：拉取最新数据并刷新"""
        if self.is_review_mode or self._is_reconfiguring:
            return
        if not self.data_processor:
            return

        # 1. 拉取数据 (从 Processor 获取已降采样的视图)
        full_data = self.data_processor.get_plot_data()
        if full_data is None or full_data.size == 0:
            return

        # 2. 准备时间轴
        # 如果时间轴尚未初始化或长度不匹配（比如刚刚重置了Processor），重新计算
        target_len = len(self._time_vector)
        current_len = full_data.shape[1]

        # 截取或补全数据以匹配时间轴
        if current_len >= target_len:
            # 取最后 target_len 个点
            display_data = full_data[:, -target_len:]
            t = self._time_vector
        else:
            # 数据不足时（刚启动），临时计算一个短的时间轴
            # 这种情况只在启动前几秒发生，性能损耗可忽略
            effective_rate = self.sample_rate / self.data_processor.downsample_factor
            t = np.linspace(0, current_len / effective_rate, current_len)
            display_data = full_data

        # 3. 绘图更新 (仅更新当前模式下的可见曲线)
        if self.current_mode == PlotMode.STACKED:
            scale = self.stacked_view_scale if abs(self.stacked_view_scale) > 1e-9 else 1e-9

            for i in range(min(self.num_channels, display_data.shape[0])):
                # 性能优化：只更新可见曲线
                if self.stacked_curves[i].isVisible():
                    offset = (self.num_channels - 1 - i) * CHANNEL_HEIGHT
                    # 矢量化计算
                    y_data = (display_data[i] / scale * CHANNEL_HEIGHT / 2) + offset
                    self.stacked_curves[i].setData(t, y_data)

        else:  # INDIVIDUAL Mode
            for i in range(min(self.num_channels, display_data.shape[0])):
                if self.individual_plots[i].isVisible():
                    self.individual_curves[i].setData(t, display_data[i])

        # 4. 处理首次自动缩放关闭
        if not self._initial_autorange_done and np.any(display_data):
            self._disable_autorange()

    def _disable_autorange(self):
        self.stacked_plot.enableAutoRange(axis='y', enable=False)
        for p in self.individual_plots:
            p.enableAutoRange(axis='y', enable=False)
        self._initial_autorange_done = True
        print("TimeDomainWidget: Auto-range disabled.")

    # --- 交互与事件处理 ---
    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sample_rate == new_rate: return
        self.sample_rate = new_rate
        self.set_plot_duration(self.plot_seconds)  # 触发重新计算时间轴

    @pyqtSlot(int)
    def set_plot_duration(self, seconds):
        if self.is_review_mode: return
        self.plot_seconds = seconds

        # 更新X轴
        self.stacked_plot.setXRange(0, self.plot_seconds)
        for p in self.individual_plots:
            p.setXRange(0, self.plot_seconds)

        # 重新计算时间缓存
        self._recalc_time_vector()

        # 更新标签位置
        for i, label in enumerate(self.stacked_labels):
            offset = (self.num_channels - 1 - i) * CHANNEL_HEIGHT
            label.setPos(-0.05 * self.plot_seconds, offset)

    def toggle_visibility(self, channel, visible):
        """切换通道可见性"""
        if 0 <= channel < self.num_channels:
            # Stacked
            if channel < len(self.stacked_curves):
                self.stacked_curves[channel].setVisible(visible)
                self.stacked_labels[channel].setVisible(visible)
            # Individual
            if channel < len(self.individual_plots):
                self.individual_plots[channel].setVisible(visible)
                # 重新排列独立视图布局
                self._update_individual_view_layout()

    def _update_individual_view_layout(self):
        """重建独立视图布局，只显示可见的 plot"""
        layout = self.individual_view.ci
        layout.clear()

        # 筛选可见图表
        visible_items = [(i, p) for i, p in enumerate(self.individual_plots) if p.isVisible()]

        for row, (idx, plot) in enumerate(visible_items):
            plot.setXLink(None);
            plot.setYLink(None)  # 解除联动

            # 恢复标签
            color = PLOT_COLORS[idx % len(PLOT_COLORS)]
            plot.setLabel('left', f"CH {idx + 1}", units='µV', color=color)
            plot.showAxis('bottom')
            plot.setLabel('bottom', 'Time', units='s')

            layout.addItem(plot, row=row, col=0)

    def _toggle_plot_mode(self):
        new_mode = PlotMode.INDIVIDUAL if self.current_mode == PlotMode.STACKED else PlotMode.STACKED
        self._set_plot_mode(new_mode)

    def _set_plot_mode(self, mode):
        # 状态同步：切换回 Stacked 时应用第一通道的缩放
        if mode == PlotMode.STACKED and self.current_mode == PlotMode.INDIVIDUAL:
            if self.individual_scales:
                self.stacked_view_scale = self.individual_scales[0]
                self._update_stacked_y_range()

        self.current_mode = mode
        if mode == PlotMode.STACKED:
            self.plot_stack.setCurrentWidget(self.stacked_view)
            self.switch_button.setText("Switch to Individual View")
        else:
            self.plot_stack.setCurrentWidget(self.individual_view)
            self.switch_button.setText("Switch to Stacked View")

        # 切换模式后立即重绘（如果在回放模式）
        if self.is_review_mode:
            self._redraw_static()

    # --- 缩放与范围处理 ---
    def _update_stacked_y_range(self):
        if self._is_updating_stacked_range or not hasattr(self, 'stacked_plot'): return
        self._is_updating_stacked_range = True
        # 计算总高度范围
        total_height = self.num_channels * CHANNEL_HEIGHT * (200.0 / self.stacked_view_scale)
        # 设置范围，留出一点余量
        self.stacked_plot.setYRange(-total_height / self.num_channels, total_height)
        self._is_updating_stacked_range = False

    def _on_stacked_y_range_changed(self):
        """用户缩放 Stacked 视图时反算 scale"""
        if self._is_updating_stacked_range or self._is_reconfiguring: return
        self._is_updating_stacked_range = True

        y_range = self.stacked_plot.getViewBox().viewRange()[1]
        visible_height = y_range[1] - y_range[0]

        if abs(visible_height) > 1e-9:
            self.stacked_view_scale = (self.num_channels * CHANNEL_HEIGHT * 200.0) / visible_height

        if self.is_review_mode: self._redraw_static()
        self._is_updating_stacked_range = False

    def _on_individual_y_range_changed(self, channel_index):
        """用户缩放 Individual 视图时记录 scale"""
        if channel_index >= len(self.individual_plots): return
        plot = self.individual_plots[channel_index]

        if plot.getAxis('left').scene():  # 确保对象存活
            y_range = plot.getViewBox().viewRange()[1]
            self.individual_scales[channel_index] = (y_range[1] - y_range[0]) / 2

    @pyqtSlot(int, float)
    def adjust_scale(self, channel, new_scale):
        """外部调用（如滚轮或设置）调整缩放"""
        if not (0 <= channel < self.num_channels): return

        self.individual_scales[channel] = new_scale
        if self.current_mode == PlotMode.INDIVIDUAL:
            self.individual_plots[channel].setYRange(-new_scale, new_scale)
        elif self.current_mode == PlotMode.STACKED:
            self.stacked_view_scale = new_scale
            self._update_stacked_y_range()
            if self.is_review_mode: self._redraw_static()

    # --- 回放/静态模式逻辑 ---
    def display_static_data(self, data, sampling_rate, markers=None, channel_names=None):
        """进入回放模式显示静态数据"""
        self.is_review_mode = True
        self.stop_updates()  # 停止实时刷新

        num_channels, num_samples = data.shape
        self.reconfigure_channels(num_channels)
        self.clear_plots(for_static=True)  # 清理 Marker

        # 保存静态数据
        self.static_data = data
        duration = num_samples / sampling_rate
        self.static_time_vector = np.arange(num_samples) / sampling_rate

        # 自动设置初始缩放
        max_val = np.max(np.abs(data)) if np.any(data) else 200.0
        if max_val < 1e-9: max_val = 200.0

        self.stacked_view_scale = max_val
        self.individual_scales = [max_val] * num_channels

        # 设置视图范围
        self.stacked_plot.setXRange(0, duration)
        self._update_stacked_y_range()

        for p in self.individual_plots:
            p.setXRange(0, duration)
            p.setYRange(-max_val, max_val)

        # 更新标签位置
        for i, label in enumerate(self.stacked_labels):
            offset = (self.num_channels - 1 - i) * CHANNEL_HEIGHT
            label.setPos(-0.05 * duration, offset)

        # 绘制数据
        self._redraw_static()

        # 更新名称
        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)

        # 绘制 Marker
        if markers and 'timestamps' in markers:
            self._draw_static_markers(markers, sampling_rate)

    def _redraw_static(self):
        """重绘静态数据（用于回放模式下的缩放/切换）"""
        if self.static_data is None: return

        t = self.static_time_vector
        data = self.static_data

        if self.current_mode == PlotMode.STACKED:
            scale = self.stacked_view_scale if abs(self.stacked_view_scale) > 1e-9 else 1e-9
            for i in range(self.num_channels):
                offset = (self.num_channels - 1 - i) * CHANNEL_HEIGHT
                y = (data[i] / scale * CHANNEL_HEIGHT / 2) + offset
                self.stacked_curves[i].setData(t, y)
        else:
            for i in range(self.num_channels):
                self.individual_curves[i].setData(t, data[i])

    def _draw_static_markers(self, markers, fs):
        timestamps, labels = markers['timestamps'], markers['labels']
        pen = pg.mkPen('r', style=pg.QtCore.Qt.PenStyle.DashLine, width=1)

        for ts, lbl in zip(timestamps, labels):
            t_sec = float(ts) / fs
            # Stacked Marker
            l1 = pg.InfiniteLine(pos=t_sec, angle=90, pen=pen, label=str(lbl),
                                 labelOpts={'position': 0.1, 'color': 'r', 'movable': True})
            self.stacked_plot.addItem(l1)
            self.marker_lines.append(l1)

            # Individual Markers
            for p in self.individual_plots:
                l2 = pg.InfiniteLine(pos=t_sec, angle=90, pen=pen, label=str(lbl),
                                     labelOpts={'position': 0.1, 'color': 'r', 'movable': True})
                p.addItem(l2)
                self.marker_lines.append(l2)

    # --- 工具方法 ---
    @pyqtSlot(int, str)
    def update_channel_name(self, channel, new_name):
        if not (0 <= channel < self.num_channels): return

        # Stacked
        if channel < len(self.stacked_labels):
            self.stacked_labels[channel].setText(new_name)
        # Individual
        if channel < len(self.individual_plots):
            self.individual_plots[channel].getAxis('left').setLabel(new_name, units='µV')

    @pyqtSlot()
    def show_live_marker(self):
        """显示实时 Marker 动画"""
        pos = self.plot_seconds
        pen = pg.mkPen('g', style=pg.QtCore.Qt.PenStyle.DashLine, width=2)

        lines = []
        if self.current_mode == PlotMode.STACKED:
            line = pg.InfiniteLine(pos=pos, angle=90, pen=pen)
            self.stacked_plot.addItem(line)
            lines.append(line)
        else:
            for p in self.individual_plots:
                if p.isVisible():
                    line = pg.InfiniteLine(pos=pos, angle=90, pen=pen)
                    p.addItem(line)
                    lines.append(line)

        self.temp_marker_lines.extend(lines)
        # 1.5秒后自动消失
        QTimer.singleShot(1500, partial(self._remove_temp_lines, lines))

    def _remove_temp_lines(self, lines):
        for line in lines:
            if line.scene(): line.scene().removeItem(line)
            if line in self.temp_marker_lines: self.temp_marker_lines.remove(line)

    def clear_plots(self, for_static=False):
        """清理绘图内容"""
        # 清理 Markers
        for line in self.marker_lines:
            if line.scene(): line.scene().removeItem(line)
        self.marker_lines.clear()

        if not for_static:
            self.is_review_mode = False
            self.static_data = None
            self._initial_autorange_done = False

            # 清空曲线
            empty = np.array([])
            for c in self.stacked_curves: c.setData(empty, empty)
            for c in self.individual_curves: c.setData(empty, empty)

            self.stacked_plot.enableAutoRange(axis='y', enable=True)
            for p in self.individual_plots: p.enableAutoRange(axis='y', enable=True)