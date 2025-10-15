# Create new file: ui/widgets/review_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from .time_domain_widget import TimeDomainWidget
from .frequency_domain_widget import FrequencyDomainWidget

class ReviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Review")
        self.setGeometry(100, 100, 1600, 900) # Give it a good default size

        # Create its own independent plot widgets
        self.time_domain_widget = TimeDomainWidget()
        self.frequency_domain_widget = FrequencyDomainWidget()

        # Set up the layout for this dialog
        layout = QVBoxLayout(self)
        layout.addWidget(self.time_domain_widget, 2)  # Time domain gets more space
        layout.addWidget(self.frequency_domain_widget, 1)

    def load_and_display(self, result_dict):
        """
        Public method to populate the plots with data from a loaded file.
        """
        if 'error' in result_dict:
            self.setWindowTitle(f"Error Loading File: {result_dict['error']}")
            return

        self.time_domain_widget.display_static_data(
            result_dict['data'],
            result_dict['sampling_rate'],
            result_dict.get('markers')  # Use .get() for safety
        )
        # Use the static display methods of the plot widgets
        self.frequency_domain_widget.update_fft(result_dict['freqs'], result_dict['mags'])

        # Update the window title to show the filename
        self.setWindowTitle(f"Reviewing: {result_dict['filename']}")

        self.show() # Show the dialog as a non-modal window