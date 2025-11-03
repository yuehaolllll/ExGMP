# In ui/widgets/ica_component_dialog.py

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QScrollArea, QGridLayout,
                             QCheckBox, QLabel, QDialogButtonBox)
from PyQt6.QtCore import Qt


class ICAComponentDialog(QDialog):
    def __init__(self, components_data, sampling_rate, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Artifact Components")
        self.setMinimumSize(800, 600)

        self.components = components_data
        self.sampling_rate = sampling_rate
        self.checkboxes = []

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)

        # --- Scroll Area for plots ---
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.plot_layout = QGridLayout(scroll_content)
        self.plot_layout.setSpacing(10)
        scroll_area.setWidget(scroll_content)

        main_layout.addWidget(scroll_area)

        # --- Create plots for each component ---
        self._create_component_plots()

        # --- OK and Cancel Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_component_plots(self):
        num_components, num_samples = self.components.shape
        time_vector = np.arange(num_samples) / self.sampling_rate

        linked_plot_view = None  # To link all X-axes

        for i in range(num_components):
            # --- UI Elements for one component ---
            checkbox = QCheckBox(f"Component {i}")
            plot_widget = pg.PlotWidget()
            plot_widget.setMinimumHeight(150)  # Give each plot some space

            # --- Plotting ---
            plot_widget.plot(time_vector, self.components[i], pen='b')
            plot_widget.setLabel('left', 'Amplitude')
            plot_widget.setLabel('bottom', 'Time', units='s')
            plot_widget.setTitle(f"Independent Component {i}")
            plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # --- Link X-Axes ---
            if linked_plot_view is None:
                linked_plot_view = plot_widget.getViewBox()
            else:
                plot_widget.setXLink(linked_plot_view)

            # --- Layout ---
            self.plot_layout.addWidget(checkbox, i, 0, Qt.AlignmentFlag.AlignTop)
            self.plot_layout.addWidget(plot_widget, i, 1)

            self.checkboxes.append(checkbox)

    def get_selected_indices(self):
        """Returns a list of indices for the checked components."""
        selected = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                selected.append(i)
        return selected