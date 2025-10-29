from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLineEdit, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt

# T9 Layout data remains the same
T9_LAYOUT = {
    1: ("1.,?!", "1.,?!"), 2: ("ABC2", "ABC2"), 3: ("DEF3", "DEF3"),
    4: ("GHI4", "GHI4"), 5: ("JKL5", "JKL5"), 6: ("MNO6", "MNO6"),
    7: ("PQRS7", "PQRS7"), 8: ("TUV8", "TUV8"), 9: ("WXYZ9", "WXYZ9"),
    "*": ("*", "*"), 0: ("Space", " "), "#": ("Bksp", "<--")
}

# --- NEW, GOOGLE KEYBOARD (GBOARD) INSPIRED STYLESHEET ---
EYE_TYPING_STYLE = """
/* Main Dialog: Dark gray background */
#EyeTypingDialog {
    background-color: #202124; /* Gboard's dark background */
    border-radius: 12px;
}

/* Text Display Area */
QLineEdit {
    background-color: #202124;
    border: none;
    padding: 20px 15px;
    color: #E8EAED; /* Gboard's light text */
    font-size: 28px;
    font-family: "Segoe UI", "Roboto", sans-serif;
}

/* Container for the grid keyboard (no visible style needed) */
#GridContainer {
    background-color: transparent;
    padding: 0px;
}

/* General style for ALL grid buttons */
QPushButton#GridButton {
    background-color: #43464A; /* Gboard's key color */
    border: none;
    border-radius: 8px;
    color: #E8EAED;
    font-size: 18px;
    font-weight: 500; /* Medium weight, not too bold */
    min-height: 75px;
}

/* Style for special keys like Space and Backspace */
QPushButton#SpecialKey {
    background-color: #686B6F; /* Lighter gray for function keys */
}

/* Highlighted (selected) grid button */
QPushButton#GridButton[highlighted="true"],
QPushButton#SpecialKey[highlighted="true"] {
    background-color: #8AB4F8; /* Gboard's iconic blue highlight */
    color: #202124; /* Dark text on highlight */
}

/* Character selection bubble container */
#CharBubble {
    background-color: transparent;
    min-height: 70px; /* Reserve space */
}
#CharBubble[visible="true"] {
    background-color: #8AB4F8; /* Blue background for the bubble */
    border-radius: 10px;
}

/* Character labels inside the bubble */
#CharLabel {
    color: #202124; /* Dark text on blue background */
    font-size: 24px;
    font-weight: bold;
    padding: 10px 15px;
    border-radius: 8px;
}
#CharLabel[highlighted="true"] {
    background-color: #FFFFFF; /* White highlight for selected char */
    color: #202124;
}

/* Simulation/Control buttons at the bottom */
QPushButton#ControlButton {
    background-color: #282A2C;
    border: 1px solid #43464A;
    border-radius: 6px;
    color: #BDC1C6;
    font-size: 11px;
    font-weight: normal;
    padding: 8px 0;
    min-height: 0;
}
QPushButton#ControlButton:pressed {
    background-color: #8AB4F8;
    color: #202124;
}
"""


class EyeTypingWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Eye Typing Interface")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("EyeTypingDialog")
        self.setStyleSheet(EYE_TYPING_STYLE)
        self.setFixedSize(420, 680)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self._create_title_bar(main_layout)

        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.display)

        self.char_bubble = QWidget(self)
        self.char_bubble.setObjectName("CharBubble")
        self.char_bubble_layout = QHBoxLayout(self.char_bubble)
        self.char_bubble_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_bubble_layout.setSpacing(5)
        self.char_bubble.setProperty("visible", False)
        main_layout.addWidget(self.char_bubble)

        grid_container = QWidget()
        grid_container.setObjectName("GridContainer")
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(10)
        main_layout.addWidget(grid_container, 1)

        self.key_buttons = {}
        positions = [((i - 1) // 3, (i - 1) % 3) for i in range(1, 10)] + [(3, 0), (3, 1), (3, 2)]
        keys = list(range(1, 10)) + ['*', 0, '#']
        for key, pos in zip(keys, positions):
            text, _ = T9_LAYOUT[key]
            button = QPushButton(text)

            # --- KEY CHANGE: Assign different object names for styling ---
            if key in [0, '#']:  # Space and Backspace
                button.setObjectName("SpecialKey")
            else:
                button.setObjectName("GridButton")

            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            grid_layout.addWidget(button, pos[0], pos[1])
            self.key_buttons[key] = button

        self.STATE_GRID, self.STATE_CHAR = 0, 1
        self.current_state = self.STATE_GRID
        self.grid_pos = [1, 1]
        self.grid_map = [[1, 2, 3], [4, 5, 6], [7, 8, 9], ['*', 0, '#']]
        self.current_char_options, self.char_pos = [], 0

        self._create_control_buttons(main_layout)
        self._update_highlight()

    def _create_title_bar(self, parent_layout):
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(5, 0, 0, 0)
        title_label = QLabel("Eye Typing Interface")
        title_label.setStyleSheet("color: #9AA0A6; font-weight: 500; font-size: 14px;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; color: #9AA0A6; font-size: 18px; }
            QPushButton:hover { color: #F28B82; } /* Gboard's red for close/delete */
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)
        parent_layout.addWidget(title_bar)

    def _create_control_buttons(self, parent_layout):
        control_container = QWidget()
        control_layout = QHBoxLayout(control_container)
        control_layout.setSpacing(8)
        btn_map = {"◀": "LEFT", "▲": "UP", "OK": "BLINK_TWICE", "▼": "DOWN", "▶": "RIGHT", "Bk": "BLINK_THREE"}
        for text, command in btn_map.items():
            btn = QPushButton(text)
            btn.setObjectName("ControlButton")
            btn.clicked.connect(lambda _, cmd=command: self.on_prediction_received(cmd))
            control_layout.addWidget(btn)
        parent_layout.addWidget(control_container)

    def on_prediction_received(self, command):
        if self.current_state == self.STATE_GRID:
            if command == "UP":
                self.grid_pos[0] = max(0, self.grid_pos[0] - 1)
            elif command == "DOWN":
                self.grid_pos[0] = min(3, self.grid_pos[0] + 1)
            elif command == "LEFT":
                self.grid_pos[1] = max(0, self.grid_pos[1] - 1)
            elif command == "RIGHT":
                self.grid_pos[1] = min(2, self.grid_pos[1] + 1)
            elif command == "BLINK_TWICE":
                self._select_key()
            elif command == "BLINK_THREE":
                self._backspace()
        elif self.current_state == self.STATE_CHAR:
            if command == "LEFT":
                self.char_pos = max(0, self.char_pos - 1)
            elif command == "RIGHT":
                self.char_pos = min(len(self.current_char_options) - 1, self.char_pos + 1)
            elif command == "BLINK_TWICE":
                self._select_char()
            elif command == "BLINK_THREE":
                self._go_back_to_grid()
        self._update_highlight()

    def _select_key(self):
        key = self.grid_map[self.grid_pos[0]][self.grid_pos[1]]
        _, chars = T9_LAYOUT[key]
        if chars == "<--": self._backspace(); return
        if chars == " ": self.display.setText(self.display.text() + " "); return

        self.current_char_options = list(chars)
        self.char_pos = 0
        self.current_state = self.STATE_CHAR
        self._populate_char_bubble()
        self.char_bubble.setProperty("visible", True)

    def _select_char(self):
        selected_char = self.current_char_options[self.char_pos]
        self.display.setText(self.display.text() + selected_char)
        self._go_back_to_grid()

    def _go_back_to_grid(self):
        self.current_state = self.STATE_GRID
        self.char_bubble.setProperty("visible", False)
        # Clear bubble content for a cleaner look
        for i in reversed(range(self.char_bubble_layout.count())):
            self.char_bubble_layout.itemAt(i).widget().deleteLater()

    def _backspace(self):
        self.display.setText(self.display.text()[:-1])

    def _populate_char_bubble(self):
        for i in reversed(range(self.char_bubble_layout.count())):
            self.char_bubble_layout.itemAt(i).widget().deleteLater()
        for char in self.current_char_options:
            label = QLabel(char)
            label.setObjectName("CharLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.char_bubble_layout.addWidget(label)

    def _update_highlight(self):
        # Update grid buttons
        for key, button in self.key_buttons.items():
            is_hl = (self.current_state == self.STATE_GRID and
                     self.grid_map[self.grid_pos[0]][self.grid_pos[1]] == key)
            button.setProperty("highlighted", is_hl)

        # Update char labels
        if self.current_state == self.STATE_CHAR:
            for i in range(self.char_bubble_layout.count()):
                widget = self.char_bubble_layout.itemAt(i).widget()
                widget.setProperty("highlighted", i == self.char_pos)

        # Polish everything to apply new styles
        self.style().polish(self)
        for widget in self.findChildren(QWidget):
            self.style().polish(widget)

    # Allow moving the frameless window
    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()