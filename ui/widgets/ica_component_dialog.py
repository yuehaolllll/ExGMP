# In ui/widgets/ica_component_dialog.py

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QScrollArea, QGridLayout,
                             QCheckBox, QDialogButtonBox)
from PyQt6.QtCore import Qt
from scipy import signal


class ICAComponentDialog(QDialog):
    def __init__(self, components_data, sampling_rate, parent=None, suggested_indices=None):
        super().__init__(parent)
        self.setWindowTitle("Select Artifact Components")
        self.setMinimumSize(1200, 700)

        self.components = components_data
        self.sampling_rate = sampling_rate
        self.suggested_indices = suggested_indices or []
        self.checkboxes = []

        main_layout = QVBoxLayout(self)

        # 创建一个带滚动条的区域
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.plot_layout = QGridLayout(scroll_content)
        self.plot_layout.setSpacing(10)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 为每个成分创建图表
        self._create_component_plots()

        # OK 和 Cancel 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_component_plots(self):
        num_components, num_samples = self.components.shape
        time_vector = np.arange(num_samples) / self.sampling_rate

        linked_time_plot_view = None

        for i in range(num_components):
            checkbox = QCheckBox(f"Component {i}")

            # --- 自动勾选建议的伪迹 ---
            if i in self.suggested_indices:
                checkbox.setChecked(True)
                # 您甚至可以改变标签来提示用户这是自动检测到的
                checkbox.setText(f"Component {i} (Suggested Artifact)")

            # --- 1. 时域图 (和以前一样) ---
            time_plot_widget = pg.PlotWidget()
            time_plot_widget.setMinimumHeight(150)
            time_plot_widget.plot(time_vector, self.components[i], pen='b')
            time_plot_widget.setLabel('left', 'Amplitude')
            time_plot_widget.setLabel('bottom', 'Time', units='s')
            time_plot_widget.setTitle(f"IC {i} - Time Domain")
            time_plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # 链接所有时域图的X轴
            if linked_time_plot_view is None:
                linked_time_plot_view = time_plot_widget.getViewBox()
            else:
                time_plot_widget.setXLink(linked_time_plot_view)

            # --- 2. 新增：功率谱密度(PSD)图 ---
            psd_plot_widget = pg.PlotWidget()
            psd_plot_widget.setMinimumHeight(150)

            # 使用 Welch 方法计算PSD
            # nperseg: 每个段的长度，这里设为采样率，意味着1秒的窗口
            freqs, psd = signal.welch(self.components[i], fs=self.sampling_rate, nperseg=self.sampling_rate)

            psd_plot_widget.plot(freqs, psd, pen='g')
            psd_plot_widget.setLabel('left', 'Power Spectral Density')
            psd_plot_widget.setLabel('bottom', 'Frequency', units='Hz')
            psd_plot_widget.setTitle(f"IC {i} - Frequency Domain")
            psd_plot_widget.setLogMode(x=False, y=True)  # Y轴使用对数刻度更易于观察
            psd_plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # --- 3. 将所有控件添加到网格布局中 ---
            self.plot_layout.addWidget(checkbox, i, 0, Qt.AlignmentFlag.AlignTop)
            self.plot_layout.addWidget(time_plot_widget, i, 1)
            self.plot_layout.addWidget(psd_plot_widget, i, 2)  # 将PSD图添加到第2列

            self.checkboxes.append(checkbox)

    def get_selected_indices(self):
        """返回被勾选的成分的索引列表"""
        return [i for i, checkbox in enumerate(self.checkboxes) if checkbox.isChecked()]