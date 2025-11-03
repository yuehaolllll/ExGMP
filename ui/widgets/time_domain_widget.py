# In ui/widgets/time_domain_widget.py
import pyqtgraph as pg
import numpy as np
import collections
from pyqtgraph.Qt import QtWidgets
from PyQt6.QtCore import QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QStackedLayout, QHBoxLayout, QGridLayout
from enum import Enum
from functools import partial

# 绘图模式
class PlotMode(Enum):
    INDIVIDUAL = 1
    STACKED = 2

# --- 常量 ---
NUM_CHANNELS = 8
#SAMPLING_RATE = 2000
DOWNSAMPLE_FACTOR = 10

PLOT_COLORS = [
    "#007BFF",  # Blue
    "#28A745",  # Green
    "#DC3545",  # Red
    "#17A2B8",  # Teal
    "#FD7E14",  # Orange
    "#6F42C1",  # Purple
    "#343A40",  # Dark Gray
    "#E83E8C",  # Pink
]

CHANNEL_HEIGHT = 1.0

class TimeDomainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 状态管理 ---
        self.is_review_mode = False
        self.static_data = None
        self.static_time_vector = None
        self.current_mode = PlotMode.STACKED
        self.plot_seconds = 5
        self.sampling_rate = 1000  # 默认值
        self.plot_window_samples = int(self.sampling_rate * self.plot_seconds)
        self.individual_scales = [200.0] * NUM_CHANNELS
        self.stacked_view_scale = 200.0
        self._is_updating_stacked_range = False
        self.data_buffers = [
            collections.deque(np.zeros(self.plot_window_samples), maxlen=self.plot_window_samples)
            for _ in range(NUM_CHANNELS)
        ]
        self.marker_lines, self.temp_marker_lines = [], []

        # --- UI 布局 ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        button_bar_layout = QHBoxLayout()

        # 切换视图
        self.switch_button = QPushButton("Switch to Individual View")
        self.switch_button.setFixedWidth(180)
        self.switch_button.clicked.connect(self._toggle_plot_mode)

        button_bar_layout.addStretch()
        button_bar_layout.addWidget(self.switch_button)
        main_layout.addLayout(button_bar_layout)

        self.plot_stack = pg.QtWidgets.QStackedWidget()
        main_layout.addWidget(self.plot_stack)

        # --- 创建两个独立的 GraphicsLayoutWidget 实例 ---
        self.stacked_view = self._create_stacked_view()
        self.individual_view = self._create_individual_view()

        self.plot_stack.addWidget(self.stacked_view)
        self.plot_stack.addWidget(self.individual_view)

        self._update_individual_view_layout()
        self._set_plot_mode(self.current_mode)

    @pyqtSlot(int)
    def set_sample_rate(self, new_rate):
        if self.sampling_rate == new_rate: return
        self.sampling_rate = new_rate
        # 当采样率变化时，重新计算绘图窗口的点数
        self.set_plot_duration(self.plot_seconds)

    def _create_stacked_view(self):
        view = pg.GraphicsLayoutWidget()
        self.stacked_plot = view.addPlot(row=0, col=0)

        self.stacked_plot.setDownsampling(mode='peak')
        self.stacked_plot.setClipToView(True)

        self.stacked_plot.setLabel('bottom', 'Time', units='s')
        self.stacked_plot.hideAxis('left')
        self.stacked_plot.showGrid(x=True, y=True, alpha=0.4)
        self.stacked_plot.getViewBox().setMouseEnabled(y=True)
        self.stacked_plot.getViewBox().sigYRangeChanged.connect(self._on_stacked_y_range_changed)
        self._update_stacked_y_range()
        self.stacked_curves, self.stacked_labels = [], []
        for i in range(NUM_CHANNELS):
            offset = (NUM_CHANNELS - 1 - i) * CHANNEL_HEIGHT
            curve = self.stacked_plot.plot(pen=pg.mkPen(color=PLOT_COLORS[i], width=1.5))
            label = pg.TextItem(f"CH {i+1}", color=PLOT_COLORS[i], anchor=(0, 0.5))
            label.setPos(-0.05 * self.plot_seconds, offset)
            self.stacked_plot.addItem(label)
            self.stacked_curves.append(curve)
            self.stacked_labels.append(label)
        return view

    def _create_individual_view(self):
        view = pg.GraphicsLayoutWidget()
        view.ci.layout.setSpacing(2)

        self.individual_plots = []
        self.individual_curves = []

        # Create all 8 PlotItems once and store them
        for i in range(NUM_CHANNELS):
            p = pg.PlotItem()
            p.setDownsampling(mode='peak');
            p.setClipToView(True)
            #p.getAxis('bottom').setPen(pg.mkPen(color='#DCDCDC', width=1))
            p.showGrid(x=True, y=True, alpha=0.3)
            p.setYRange(-self.individual_scales[i], self.individual_scales[i])
            p.getViewBox().setMouseEnabled(x=True, y=True)  # Enable mouse for both axes
            p.getViewBox().sigYRangeChanged.connect(partial(self._on_individual_y_range_changed, i))

            curve = p.plot(pen=pg.mkPen(color=PLOT_COLORS[i], width=1.5))

            self.individual_plots.append(p)
            self.individual_curves.append(curve)

        return view

    def toggle_visibility(self, channel, visible):
        # Stacked View logic (correct)
        if 0 <= channel < len(self.stacked_curves):
            self.stacked_curves[channel].setVisible(visible)
            self.stacked_labels[channel].setVisible(visible)

        # Individual View: Hide/Show the PlotItem and trigger a full layout rebuild
        if 0 <= channel < len(self.individual_plots):
            self.individual_plots[channel].setVisible(visible)
            self._update_individual_view_layout()

    def _update_individual_view_layout(self):
        """Dynamically rebuilds the layout for a clean, correct, and independent view."""
        layout = self.individual_view.ci
        layout.clear()

        visible_plots = [p for p in self.individual_plots if p.isVisible()]

        for i, plot in enumerate(visible_plots):
            channel_index = self.individual_plots.index(plot)

            # --- 核心修改部分 ---
            # 1. 强制解除任何现有的轴联动，确保每个图表的X轴和Y轴都是独立的
            plot.setXLink(None)
            plot.setYLink(None)

            # 2. 重新应用Y轴标签，防止它在布局重建时丢失
            plot.setLabel('left', f"CH {channel_index + 1}", units='µV', color=PLOT_COLORS[channel_index])

            # 3. (修改点) 无条件地为每一个可见的图表显示其独立的X轴
            plot.showAxis('bottom')
            plot.setLabel('bottom', 'Time', units='s')

            # --- 原来的条件隐藏逻辑已被上面两行代码替代 ---
            # if i < len(visible_plots) - 1:
            #     plot.hideAxis('bottom')
            # else:
            #     plot.showAxis('bottom')
            #     plot.setLabel('bottom', 'Time', units='s')

            # 4. 将配置好的图表添加到布局的下一行
            layout.addItem(plot, row=i, col=0)

    def _update_stacked_y_range(self):
        """根据当前的 stacked_view_scale 来更新Y轴的可见范围"""
        if self._is_updating_stacked_range: return
        self._is_updating_stacked_range = True

        # 计算总高度，使其与缩放因子成反比
        # 缩放因子越小 (信号放大)，总高度越大
        total_height = NUM_CHANNELS * CHANNEL_HEIGHT * (200.0 / self.stacked_view_scale)
        self.stacked_plot.setYRange(-total_height / NUM_CHANNELS, total_height)

        self._is_updating_stacked_range = False

    def _on_stacked_y_range_changed(self):
        if self._is_updating_stacked_range: return
        self._is_updating_stacked_range = True
        y_range = self.stacked_plot.getViewBox().viewRange()[1]
        visible_height = y_range[1] - y_range[0]
        if abs(visible_height) > 1e-9:
            self.stacked_view_scale = (NUM_CHANNELS * CHANNEL_HEIGHT * 200.0) / visible_height
        if not self.is_review_mode: self._redraw_stacked()
        self._is_updating_stacked_range = False

    def _on_individual_y_range_changed(self, channel_index):
        plot_item = self.individual_plots[channel_index]
        # Check if the axis is part of a scene; a robust way to check if it's "alive"
        if plot_item.getAxis('left').scene() is not None:
            y_range = plot_item.getViewBox().viewRange()[1]
            new_scale = (y_range[1] - y_range[0]) / 2
            self.individual_scales[channel_index] = new_scale

    def _toggle_plot_mode(self):
        if self.current_mode == PlotMode.STACKED:
            self._set_plot_mode(PlotMode.INDIVIDUAL)
        else:
            self._set_plot_mode(PlotMode.STACKED)

    def _set_plot_mode(self, mode):
        # 状态同步逻辑
        if mode == PlotMode.STACKED and self.current_mode == PlotMode.INDIVIDUAL:
            self.stacked_view_scale = self.individual_scales[0]
            self._update_stacked_y_range()

        self.current_mode = mode
        if mode == PlotMode.STACKED:
            self.plot_stack.setCurrentWidget(self.stacked_view)
            self.switch_button.setText("Switch to Individual View")
        else:
            self.plot_stack.setCurrentWidget(self.individual_view)
            self.switch_button.setText("Switch to Stacked View")

        # 切换后，立即使用【正确的数据源】重绘
        self._redraw_all_channels()

    def _redraw_all_channels(self):
        if self.current_mode == PlotMode.STACKED: self._redraw_stacked()
        else: self._redraw_individual()

    def _redraw_stacked(self):
        if self.is_review_mode:
            if self.static_data is None: return
            data_source = self.static_data
            time_vector = self.static_time_vector
        else:
            current_samples = len(self.data_buffers[0])
            if current_samples == 0: return
            data_source = [np.array(buf) for buf in self.data_buffers]
            # 时间轴现在直接根据真实采样率计算
            time_vector = np.linspace(0, self.plot_seconds, current_samples)

        scale = self.stacked_view_scale
        if abs(scale) < 1e-9: scale = 1e-9
        for i in range(NUM_CHANNELS):
            offset = (NUM_CHANNELS - 1 - i) * CHANNEL_HEIGHT
            scaled_data = (data_source[i] / scale * CHANNEL_HEIGHT / 2) + offset
            self.stacked_curves[i].setData(x=time_vector, y=scaled_data)

    def _redraw_individual(self):
        if self.is_review_mode:
            if self.static_data is None: return
            data_source = self.static_data
            time_vector = self.static_time_vector
        else:
            current_samples = len(self.data_buffers[0])
            if current_samples == 0: return
            data_source = [np.array(buf) for buf in self.data_buffers]
            # 时间轴现在直接根据真实采样率计算
            time_vector = np.linspace(0, self.plot_seconds, current_samples)

        for i in range(NUM_CHANNELS):
            self.individual_curves[i].setData(x=time_vector, y=data_source[i])

    def update_plot(self, data_chunk):
        if self.is_review_mode: return # 回顾模式下忽略新的实时数据
        for i in range(NUM_CHANNELS): self.data_buffers[i].extend(data_chunk[i])
        self._redraw_all_channels()

    @pyqtSlot(int, str)
    def update_channel_name(self, channel, new_name):
        """
        更新两种视图模式下对应通道的名称。
        """
        # 安全检查，确保 channel 索引有效
        if 0 <= channel < NUM_CHANNELS:

            # --- 核心修复：操作正确的、用户可见的UI组件 ---

            # 1. 更新“独立视图”(Individual View)中对应图表的Y轴标签
            #    self.individual_plots 是在 _create_individual_view 中创建的图表列表
            if hasattr(self, 'individual_plots') and channel < len(self.individual_plots):
                axis = self.individual_plots[channel].getAxis('left')
                axis.setLabel(new_name, units='µV')

            # 2. 更新“堆叠视图”(Stacked View)中对应通道的文本标签
            #    self.stacked_labels 是在 _create_stacked_view 中创建的 TextItem 列表
            if hasattr(self, 'stacked_labels') and channel < len(self.stacked_labels):
                self.stacked_labels[channel].setText(new_name)

            print(f"TimeDomainWidget: Updated channel {channel} name to '{new_name}' in both views.")

    @pyqtSlot(int)
    def set_plot_duration(self, seconds):
        if self.is_review_mode: return

        # 不再除以 DOWNSAMPLE_FACTOR
        self.plot_seconds = seconds
        self.plot_window_samples = int(self.sampling_rate * self.plot_seconds)

        # 更新X轴范围
        for p in self.individual_plots: p.setXRange(0, self.plot_seconds)
        self.stacked_plot.setXRange(0, self.plot_seconds)

        # 更新标签位置
        for i, label in enumerate(self.stacked_labels):
            offset = (NUM_CHANNELS - 1 - i) * CHANNEL_HEIGHT
            label.setPos(-0.05 * self.plot_seconds, offset)

        # 重建缓冲区以适应新的长度
        for i in range(NUM_CHANNELS):
            current_data = list(self.data_buffers[i])
            new_buffer = collections.deque(maxlen=self.plot_window_samples)
            new_buffer.extend(current_data)
            self.data_buffers[i] = new_buffer

        self._redraw_all_channels()

    @pyqtSlot(int, float)
    def adjust_scale(self, channel, new_scale):
        if 0 <= channel < NUM_CHANNELS:
            self.individual_scales[channel] = new_scale
            if self.current_mode == PlotMode.INDIVIDUAL:
                self.individual_plots[channel].setYRange(-new_scale, new_scale)
            elif self.current_mode == PlotMode.STACKED:
                self.stacked_view_scale = new_scale
                self._update_stacked_y_range()
                self._redraw_stacked()

    @pyqtSlot()
    def show_live_marker(self):
        marker_time = self.plot_seconds
        pen = pg.mkPen('g', style=pg.QtCore.Qt.PenStyle.DashLine, width=2)

        if self.current_mode == PlotMode.STACKED:
            line = pg.InfiniteLine(pos=marker_time, angle=90, pen=pen)
            self.stacked_plot.addItem(line)
            self.temp_marker_lines.append(line)
        else:
            for p in self.individual_plots:
                if p.isVisible():
                    line = pg.InfiniteLine(pos=marker_time, angle=90, pen=pen)
                    p.addItem(line)
                    self.temp_marker_lines.append(line)

        QTimer.singleShot(1500, self.remove_live_markers)

    def remove_live_markers(self):
        for line in self.temp_marker_lines:
            if line.scene(): line.scene().removeItem(line)
        self.temp_marker_lines.clear()

    def display_static_data(self, data, sampling_rate, markers=None, channel_names=None):
        self.is_review_mode = True
        self.clear_plots(for_static=True)
        num_samples = data.shape[1]
        duration = num_samples / sampling_rate
        self.static_data = data
        self.static_time_vector = np.arange(num_samples) / sampling_rate
        max_abs_val = np.max(np.abs(data))
        if max_abs_val < 1e-9: max_abs_val = 200.0
        self.stacked_view_scale = max_abs_val
        self._update_stacked_y_range()
        for i in range(NUM_CHANNELS):
            self.individual_scales[i] = max_abs_val
            self.individual_plots[i].setYRange(-max_abs_val, max_abs_val)
        self.stacked_plot.setXRange(0, duration, padding=0)
        for p in self.individual_plots: p.setXRange(0, duration, padding=0)
        for i, label in enumerate(self.stacked_labels):
            offset = (NUM_CHANNELS - 1 - i) * CHANNEL_HEIGHT
            label.setPos(-0.05 * duration, offset)
        self._redraw_all_channels()
        if channel_names:
            for i, name in enumerate(channel_names):
                self.update_channel_name(i, name)
        if markers is not None and 'timestamps' in markers and len(markers['timestamps']) > 0:
            timestamps, labels = markers['timestamps'], markers['labels']
            pen = pg.mkPen('r', style=pg.QtCore.Qt.PenStyle.DashLine, width=1)
            for ts, lbl in zip(timestamps, labels):
                marker_time = float(ts) / sampling_rate
                line1 = pg.InfiniteLine(pos=marker_time, angle=90, movable=False, pen=pen, label=str(lbl), labelOpts={'position':0.1, 'color':'r', 'movable':True})
                self.stacked_plot.addItem(line1); self.marker_lines.append(line1)
                for p in self.individual_plots:
                    line2 = pg.InfiniteLine(pos=marker_time, angle=90, movable=False, pen=pen, label=str(lbl), labelOpts={'position':0.1, 'color':'r', 'movable':True})
                    p.addItem(line2); self.marker_lines.append(line2)

    def clear_plots(self, for_static=False):
        for line in self.marker_lines:
            if line.scene():
                if self.stacked_plot and line in self.stacked_plot.items: self.stacked_plot.removeItem(line)
                for p in self.individual_plots:
                    if line in p.items: p.removeItem(line)
        self.marker_lines.clear()
        if not for_static:
            self.is_review_mode = False
            self.static_data = None
            self.static_time_vector = None
            self.set_plot_duration(5)
            for i in range(NUM_CHANNELS):
                self.data_buffers[i].clear()
                self.data_buffers[i].extend(np.zeros(self.plot_window_samples))
            self._redraw_all_channels()
