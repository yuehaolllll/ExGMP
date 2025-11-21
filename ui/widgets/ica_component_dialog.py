# File: ui/widgets/ica_component_dialog.py

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QScrollArea, QGridLayout,
                             QCheckBox, QDialogButtonBox, QLabel)
from PyQt6.QtCore import Qt
from scipy import signal


class ICAComponentDialog(QDialog):
    def __init__(self, components_data, sampling_rate, parent=None, suggested_indices=None):
        super().__init__(parent)
        self.setWindowTitle("Select Artifact Components to Remove")
        self.resize(1400, 800)  # 稍微调大默认尺寸

        self.components = components_data
        self.sampling_rate = sampling_rate
        self.suggested_indices = suggested_indices or []
        self.checkboxes = []

        main_layout = QVBoxLayout(self)

        # 顶部提示语
        hint_label = QLabel("Check the components representing artifacts (e.g., Eye Blinks). \n"
                            "Items marked in RED were automatically detected by the algorithm.")
        hint_label.setStyleSheet("font-size: 12px; color: #555; margin-bottom: 10px;")
        main_layout.addWidget(hint_label)

        # 创建一个带滚动条的区域
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)

        scroll_content = QWidget()
        self.plot_layout = QGridLayout(scroll_content)
        self.plot_layout.setSpacing(15)
        # 设置列比例：Checkbox(0) 最小，Time(1) 宽，Freq(2) 中等
        self.plot_layout.setColumnStretch(0, 0)
        self.plot_layout.setColumnStretch(1, 3)
        self.plot_layout.setColumnStretch(2, 1)

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
            # --- 0. Checkbox 设置 ---
            checkbox = QCheckBox(f"IC {i}")

            # 视觉强调建议的伪迹
            if i in self.suggested_indices:
                checkbox.setChecked(True)
                checkbox.setText(f"IC {i}\n(Artifact?)")
                # 红色粗体，醒目提示
                checkbox.setStyleSheet("QCheckBox { color: #D32F2F; font-weight: bold; }")
            else:
                checkbox.setText(f"IC {i}")

            # --- 1. 时域图 (Time Domain) ---
            time_plot = pg.PlotWidget()
            time_plot.setMinimumHeight(180)
            # 【关键优化】开启自动降采样，大幅提升渲染性能
            time_plot.setDownsampling(auto=True, mode='peak')
            time_plot.setClipToView(True)
            # 禁用菜单以提升性能
            time_plot.setMenuEnabled(False)

            time_plot.plot(time_vector, self.components[i], pen=pg.mkPen(color='#1976D2', width=1))
            time_plot.setLabel('left', 'Amp', units='au')  # ICA源是任意单位(arbitrary units)
            time_plot.setLabel('bottom', 'Time', units='s')
            time_plot.showGrid(x=True, y=True, alpha=0.2)

            # 仅允许X轴鼠标缩放，锁定Y轴（因为幅度并不重要，看波形形状即可）
            time_plot.setMouseEnabled(x=True, y=False)

            # 链接所有时域图的X轴，拖动一个，全部跟着动
            if linked_time_plot_view is None:
                linked_time_plot_view = time_plot.getViewBox()
            else:
                time_plot.setXLink(linked_time_plot_view)

            # --- 2. 频域图 (PSD) ---
            psd_plot = pg.PlotWidget()
            psd_plot.setMinimumHeight(180)
            psd_plot.setMenuEnabled(False)

            # 计算 PSD
            freqs, psd = signal.welch(self.components[i], fs=self.sampling_rate, nperseg=self.sampling_rate * 2)

            psd_plot.plot(freqs, psd, pen=pg.mkPen(color='#388E3C', width=1), fillLevel=-140, brush=(56, 142, 60, 50))
            psd_plot.setLabel('bottom', 'Freq', units='Hz')
            psd_plot.setLogMode(x=False, y=True)
            psd_plot.showGrid(x=True, y=True, alpha=0.3)

            # 【关键优化】限制显示范围到 0-120Hz，这是脑电和EOG主要能量分布区
            psd_plot.setXRange(0, 120)

            # 眨眼通常表现为低频极高能量，通过限制范围能看清楚低频部分

            # --- 3. 布局添加 ---
            # Checkbox 居中对齐
            self.plot_layout.addWidget(checkbox, i, 0, Qt.AlignmentFlag.AlignCenter)
            self.plot_layout.addWidget(time_plot, i, 1)
            self.plot_layout.addWidget(psd_plot, i, 2)

            self.checkboxes.append(checkbox)

    def get_selected_indices(self):
        """返回被勾选的成分的索引列表"""
        return [i for i, checkbox in enumerate(self.checkboxes) if checkbox.isChecked()]