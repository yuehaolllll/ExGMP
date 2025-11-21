# File: ui/widgets/eye_typing_widget.py

import sys
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLineEdit, QLabel, QFrame, QGraphicsDropShadowEffect,
                             QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont

# --- 核心数据结构 ---
# 1. 上方组 (高频元音)
GROUP_UP = {'UP': 'A', 'RIGHT': 'E', 'DOWN': 'I', 'LEFT': 'O', 'CENTER': 'U'}
# 2. 右侧组 (高频辅音)
GROUP_RIGHT = {'UP': 'T', 'RIGHT': 'N', 'DOWN': 'S', 'LEFT': 'R', 'CENTER': 'H'}
# 3. 下方组 (中频辅音)
GROUP_DOWN = {'UP': 'D', 'RIGHT': 'L', 'DOWN': 'C', 'LEFT': 'M', 'CENTER': 'W'}
# 4. 左侧组 (低频区 - 分页模式)
GROUP_LEFT_PAGES = [
    {'UP': 'G', 'RIGHT': 'F', 'DOWN': 'Y', 'LEFT': '>>', 'CENTER': 'B'},
    {'UP': 'P', 'RIGHT': 'V', 'DOWN': 'K', 'LEFT': '>>', 'CENTER': 'J'},
    {'UP': 'X', 'RIGHT': 'Q', 'DOWN': 'Z', 'LEFT': '<<', 'CENTER': ''}
]

MAIN_MENU = {
    'UP': (GROUP_UP, "AEIOU"),
    'RIGHT': (GROUP_RIGHT, "TNSRH"),
    'DOWN': (GROUP_DOWN, "DLCMW"),
    'LEFT': (GROUP_LEFT_PAGES[0], "GFY..")
}

MOCK_DICTIONARY = ["hello", "how", "are", "you", "thanks", "good", "yue", "zhi", "hao", "zoo", "quiz", "typing",
                   "interface", "system"]

COLORS = {
    "bg": "#F5F7FA",
    "surface": "#FFFFFF",
    "accent": "#03A9F4",  # 主色调蓝
    "accent_dark": "#0277BD",
    "text_main": "#37474F",
    "text_dim": "#90A4AE",
    "shadow": QColor(3, 169, 244, 60),
    "magic": "#FFC107"  # 联想词的金色
}

STYLE_SHEET = f"""
    QDialog {{ 
        background-color: {COLORS['bg']}; 
        border-radius: 16px; 
        border: 1px solid #CFD8DC; 
    }}
    QLineEdit {{
        background-color: #ECEFF1; 
        border: none; 
        border-radius: 8px;
        color: {COLORS['text_main']}; 
        font-family: "Segoe UI";
        font-size: 28px; 
        font-weight: 600; 
        padding: 12px;
        selection-background-color: {COLORS['accent']};
    }}
    QLabel {{ font-family: "Segoe UI", sans-serif; }}
"""


class CruxButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_content = QLabel()
        self.lbl_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 使用 Segoe UI Symbol 或类似字体以确保特殊字符显示美观
        self.lbl_content.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.lbl_content.setStyleSheet(f"color: {COLORS['text_main']}; background: transparent;")
        layout.addWidget(self.lbl_content)
        self.default_style()

    def default_style(self):
        self.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {COLORS['surface']}; 
                border: 1px solid #CFD8DC; 
                border-radius: 12px; 
            }}
        """)
        self.setGraphicsEffect(None)

    def highlight_style(self):
        self.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {COLORS['surface']}; 
                border: 2px solid {COLORS['accent']}; 
                border-radius: 12px; 
            }}
        """)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(20)
        glow.setColor(COLORS['shadow'])
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

    def set_highlight(self, active):
        self.highlight_style() if active else self.default_style()

    def set_map_content(self, group_data):
        u, d = group_data.get('UP', '.'), group_data.get('DOWN', '.')
        l, r = group_data.get('LEFT', '.'), group_data.get('RIGHT', '.')
        c = group_data.get('CENTER', '·')

        l_color = COLORS['accent'] if l in ['>>', '<<'] else COLORS['text_dim']
        l_weight = "bold" if l in ['>>', '<<'] else "normal"

        # 使用 HTML 表格布局，微调了字体大小和颜色
        html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style='line-height:100%;'>
            <tr><td width="33%"></td><td width="34%" align="center" style='font-size:16px; color:{COLORS['text_dim']}; padding-bottom:2px'>{u}</td><td width="33%"></td></tr>
            <tr>
                <td width="33%" align="center" style='font-size:16px; color:{l_color}; font-weight:{l_weight}; padding-right:2px'>{l}</td>
                <td width="34%" align="center" style='font-size:36px; font-weight:bold; color:{COLORS['text_main']}'>{c}</td>
                <td width="33%" align="center" style='font-size:16px; color:{COLORS['text_dim']}; padding-left:2px'>{r}</td>
            </tr>
            <tr><td width="33%"></td><td width="34%" align="center" style='font-size:16px; color:{COLORS['text_dim']}; padding-top:2px'>{d}</td><td width="33%"></td></tr>
        </table>"""
        self.lbl_content.setText(html)

    def set_single_char(self, char):
        color = COLORS['accent'] if char in ['>>', '<<'] else COLORS['text_main']
        self.lbl_content.setText(
            f"<div align='center' style='font-size:56px; font-weight:bold; color:{color}'>{char}</div>")

    def set_text_icon(self, text, color=COLORS['text_dim']):
        """设置纯文本图标"""
        self.lbl_content.setText(f"<div style='font-size:32px; color:{color}'>{text}</div>")


class EyeTypingWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(450, 720)  # 稍微加高一点点以容纳新布局
        self.setStyleSheet(STYLE_SHEET)

        self.STATE_HOME = 0
        self.STATE_GROUP = 1
        self.current_state = self.STATE_HOME

        self.active_direction = None
        self.selected_group_data = None
        self.is_paging_group = False
        self.current_page_idx = 0

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- 1. Top Bar (创新修改) ---
        top = QHBoxLayout()

        # 图标：使用 ⦿ (Bullseye/Target) 代表眼动/焦点/捕获
        # 颜色设置为主题强调色
        lbl_icon = QLabel("⦿")
        lbl_icon.setStyleSheet(f"font-size: 22px; margin-right: 6px; color: {COLORS['accent']};")

        # 标题
        lbl_title = QLabel("CRUX FLOW")
        lbl_title.setStyleSheet(f"color:{COLORS['text_main']}; font-weight:800; font-size: 16px; letter-spacing: 1px;")

        lbl_version = QLabel("v2")
        lbl_version.setStyleSheet(f"color:{COLORS['text_dim']}; font-weight:bold; font-size: 12px; margin-top: 4px;")

        # 关闭按钮：使用更优雅的细体叉号
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { 
                color: #B0BEC5; font-size: 20px; border: none; background: transparent; border-radius: 16px; 
            }
            QPushButton:hover { background-color: #FFEBEE; color: #F44336; }
        """)
        btn_close.clicked.connect(self.reject)

        top.addWidget(lbl_icon)
        top.addWidget(lbl_title)
        top.addWidget(lbl_version)
        top.addStretch()
        top.addWidget(btn_close)
        layout.addLayout(top)

        # --- 2. Suggestion Bar (创新修改) ---
        self.sugg_layout = QHBoxLayout()
        self.sugg_layout.setSpacing(10)

        # 图标：使用 ✨ (Sparkles) 代表 AI/智能预测
        # 颜色使用金色
        ai_icon = QLabel("✨")
        ai_icon.setStyleSheet(f"font-size: 18px; color: {COLORS['magic']};")
        ai_icon.setToolTip("AI Predictions Active")
        self.sugg_layout.addWidget(ai_icon)

        self.sugg_labels = []
        for _ in range(3):
            l = QLabel()
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
            self.sugg_layout.addWidget(l)
            self.sugg_labels.append(l)

        # 如果没有建议，用一个弹簧占位保持布局高度（或者直接隐藏，这里选择占位）
        self.sugg_layout.addStretch()
        layout.addLayout(self.sugg_layout)

        # --- 3. Display Area ---
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Ready...")
        # 移除焦点，防止光标闪烁干扰视线
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.display)

        # --- 4. Grid Layout ---
        grid_widget = QWidget()
        self.grid = QGridLayout(grid_widget)
        self.grid.setSpacing(12)  # 稍微紧凑一点
        self.buttons = {}

        # 放置四个方向键
        for d, (r, c) in {'UP': (0, 1), 'LEFT': (1, 0), 'RIGHT': (1, 2), 'DOWN': (2, 1)}.items():
            btn = CruxButton()
            self.grid.addWidget(btn, r, c)
            self.buttons[d] = btn

        # --- 5. Function Keys (Corner Buttons) ---

        # Backspace: 使用 ⌫
        self.btn_bs = CruxButton()
        self.btn_bs.set_text_icon("⌫", color="#EF5350")  # 红色微调，表示删除
        self.grid.addWidget(self.btn_bs, 0, 2)

        # Space: 使用 ␣
        self.btn_sp = CruxButton()
        self.btn_sp.set_text_icon("␣")
        self.grid.addWidget(self.btn_sp, 2, 2)

        # --- 6. Center Hint (Central Cross) ---
        self.center_hint = QLabel()
        self.center_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_hint.setStyleSheet(
            f"color:{COLORS['accent']}; font-weight:bold; font-size: 13px; line-height: 120%;");
        self.grid.addWidget(self.center_hint, 1, 1)

        layout.addWidget(grid_widget, 1)

        self._refresh_ui()

    def on_prediction_received(self, cmd):
        cmd = cmd.upper()
        if self.current_state == self.STATE_HOME:
            self._handle_home(cmd)
        elif self.current_state == self.STATE_GROUP:
            self._handle_group(cmd)

    def _handle_home(self, cmd):
        if cmd in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
            self.active_direction = cmd
        elif cmd == 'BLINK_TWICE':
            if self.active_direction:
                if self.active_direction == 'LEFT':
                    self.is_paging_group = True
                    self.current_page_idx = 0
                    self.selected_group_data = GROUP_LEFT_PAGES[0]
                else:
                    self.is_paging_group = False
                    self.selected_group_data = MAIN_MENU[self.active_direction][0]

                self.current_state = self.STATE_GROUP
                self.active_direction = None
        elif cmd == 'BLINK_THREE':
            txt = self.display.text()
            self.display.setText(txt[:-1])
            self._update_sugg()

        self._refresh_highlight()
        self._refresh_ui()

    def _handle_group(self, cmd):
        if cmd in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
            self.active_direction = cmd
        elif cmd == 'BLINK_TWICE':
            char = self.selected_group_data.get(self.active_direction or 'CENTER')

            if char == '>>':
                self.current_page_idx = (self.current_page_idx + 1) % len(GROUP_LEFT_PAGES)
                self.selected_group_data = GROUP_LEFT_PAGES[self.current_page_idx]
                self.active_direction = None
            elif char == '<<':
                self.current_page_idx = 0
                self.selected_group_data = GROUP_LEFT_PAGES[0]
                self.active_direction = None
            elif char:
                if char.strip():
                    self.display.setText(self.display.text() + char)
                self.current_state = self.STATE_HOME
                self.selected_group_data = None
                self.active_direction = None
                self._update_sugg()
        elif cmd == 'BLINK_THREE':
            self.current_state = self.STATE_HOME

        self._refresh_highlight()
        self._refresh_ui()

    def _refresh_ui(self):
        if self.current_state == self.STATE_HOME:
            # 使用更简洁的提示，或者用图标
            self.center_hint.setText("LOOK\nTHEN\nBLINK")
            for d, btn in self.buttons.items():
                btn.set_map_content(MAIN_MENU[d][0])
        elif self.current_state == self.STATE_GROUP:
            c = self.selected_group_data.get('CENTER', '')
            # 显示当前中心字符
            self.center_hint.setText(f"CENTER\n'{c}'")
            for d, btn in self.buttons.items():
                btn.set_single_char(self.selected_group_data.get(d, ''))

    def _refresh_highlight(self):
        for d, btn in self.buttons.items():
            btn.set_highlight(d == self.active_direction)

    def _update_sugg(self):
        txt = self.display.text().split(' ')[-1].lower()
        matches = [w for w in MOCK_DICTIONARY if w.startswith(txt)][:3] if txt else []

        if not matches:
            for l in self.sugg_labels: l.hide()
            return

        for i, l in enumerate(self.sugg_labels):
            if i < len(matches):
                l.setText(matches[i])
                l.show()
                # 建议词背景色稍微淡一点，不要太抢眼
                l.setStyleSheet(
                    f"background:#E1F5FE; color:{COLORS['accent_dark']}; padding:4px 10px; border-radius:6px; border:1px solid {COLORS['accent']}")
            else:
                l.hide()

    # 窗口拖动逻辑
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.oldPos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if hasattr(self, 'oldPos') and e.buttons() == Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = e.globalPosition().toPoint()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = EyeTypingWidget()
    w.show()


    # 键盘模拟测试
    def k(e):
        m = {Qt.Key.Key_Up: 'UP', Qt.Key.Key_Down: 'DOWN', Qt.Key.Key_Left: 'LEFT', Qt.Key.Key_Right: 'RIGHT',
             Qt.Key.Key_Return: 'BLINK_TWICE', Qt.Key.Key_Backspace: 'BLINK_THREE'}
        if e.key() in m: w.on_prediction_received(m[e.key()])


    w.keyPressEvent = k
    sys.exit(app.exec())