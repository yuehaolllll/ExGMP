import sys
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLineEdit, QLabel, QFrame, QGraphicsDropShadowEffect,
                             QSizePolicy, QStackedWidget, QApplication)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QFont
import qtawesome as qta

# --- 核心数据结构: 支持多页的十字布局 ---

# 1. 上方组 (高频元音): 5个
GROUP_UP = {'UP': 'A', 'RIGHT': 'E', 'DOWN': 'I', 'LEFT': 'O', 'CENTER': 'U'}

# 2. 右侧组 (高频辅音): 5个
GROUP_RIGHT = {'UP': 'T', 'RIGHT': 'N', 'DOWN': 'S', 'LEFT': 'R', 'CENTER': 'H'}

# 3. 下方组 (中频辅音): 5个
GROUP_DOWN = {'UP': 'D', 'RIGHT': 'L', 'DOWN': 'C', 'LEFT': 'M', 'CENTER': 'W'}

# 4. 左侧组 (低频区 - 分页模式): 剩余 11 个字母
# 逻辑：'LEFT' 方向键被征用为 "翻页 (>>)" 键
GROUP_LEFT_PAGES = [
    # Page 1: 相对常用的 (G, F, Y, B)
    {'UP': 'G', 'RIGHT': 'F', 'DOWN': 'Y', 'LEFT': '>>', 'CENTER': 'B'},
    # Page 2: 次常用的 (P, V, K, J)
    {'UP': 'P', 'RIGHT': 'V', 'DOWN': 'K', 'LEFT': '>>', 'CENTER': 'J'},
    # Page 3: 最生僻的 (X, Q, Z)
    {'UP': 'X', 'RIGHT': 'Q', 'DOWN': 'Z', 'LEFT': '<<', 'CENTER': ''}  # << 回到第一页
]

# 主菜单映射
MAIN_MENU = {
    'UP': (GROUP_UP, "AEIOU"),
    'RIGHT': (GROUP_RIGHT, "TNSRH"),
    'DOWN': (GROUP_DOWN, "DLCMW"),
    'LEFT': (GROUP_LEFT_PAGES[0], "GFY..")  # 初始显示第一页
}

MOCK_DICTIONARY = ["hello", "how", "are", "you", "thanks", "good", "yue", "zhi", "hao", "zoo", "quiz"]

COLORS = {
    "bg": "#F5F7FA", "surface": "#FFFFFF", "accent": "#03A9F4",
    "text_main": "#37474F", "text_dim": "#B0BEC5", "shadow": QColor(3, 169, 244, 60)
}

STYLE_SHEET = f"""
    QDialog {{ background-color: {COLORS['bg']}; border-radius: 20px; }}
    QLineEdit {{
        background-color: #ECEFF1; border: none; border-radius: 10px;
        color: {COLORS['text_main']}; font-size: 32px; font-weight: bold; padding: 10px;
    }}
    QLabel {{ font-family: "Segoe UI"; }}
"""


class CruxButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self);
        layout.setContentsMargins(0, 0, 0, 0);
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_content = QLabel()
        self.lbl_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_content.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.lbl_content.setStyleSheet(f"color: {COLORS['text_main']}; background: transparent;")
        layout.addWidget(self.lbl_content)
        self.default_style()

    def default_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['surface']}; border: 1px solid #CFD8DC; border-radius: 16px; }}")
        self.setGraphicsEffect(None)

    def highlight_style(self):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['surface']}; border: 3px solid {COLORS['accent']}; border-radius: 16px; }}")
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(30);
        glow.setColor(COLORS['shadow']);
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

    def set_highlight(self, active):
        self.highlight_style() if active else self.default_style()

    def set_map_content(self, group_data):
        u, d = group_data.get('UP', '.'), group_data.get('DOWN', '.')
        l, r = group_data.get('LEFT', '.'), group_data.get('RIGHT', '.')
        c = group_data.get('CENTER', '·')

        # 特殊处理翻页符号的颜色
        l_color = "#03A9F4" if l in ['>>', '<<'] else "#90A4AE"
        l_weight = "bold" if l in ['>>', '<<'] else "normal"

        html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style='line-height:120%;'>
            <tr><td width="33%"></td><td width="34%" align="center" style='font-size:18px; color:#90A4AE; padding-bottom:5px'>{u}</td><td width="33%"></td></tr>
            <tr>
                <td width="33%" align="center" style='font-size:18px; color:{l_color}; font-weight:{l_weight}; padding-right:5px'>{l}</td>
                <td width="34%" align="center" style='font-size:40px; font-weight:bold; color:#37474F'>{c}</td>
                <td width="33%" align="center" style='font-size:18px; color:#90A4AE; padding-left:5px'>{r}</td>
            </tr>
            <tr><td width="33%"></td><td width="34%" align="center" style='font-size:18px; color:#90A4AE; padding-top:5px'>{d}</td><td width="33%"></td></tr>
        </table>"""
        self.lbl_content.setText(html)

    def set_single_char(self, char):
        color = "#03A9F4" if char in ['>>', '<<'] else "#37474F"
        self.lbl_content.setText(
            f"<div align='center' style='font-size:60px; font-weight:bold; color:{color}'>{char}</div>")

    def set_icon(self, icon_name):
        icon = qta.icon(icon_name, color=COLORS['text_main'])
        self.lbl_content.setPixmap(icon.pixmap(QSize(48, 48)))


class EyeTypingWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(450, 700)
        self.setStyleSheet(STYLE_SHEET)

        self.STATE_HOME = 0
        self.STATE_GROUP = 1
        self.current_state = self.STATE_HOME

        self.active_direction = None
        self.selected_group_data = None

        # 分页状态
        self.is_paging_group = False  # 当前是否在左侧翻页组
        self.current_page_idx = 0

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self);
        layout.setContentsMargins(20, 20, 20, 20)

        top = QHBoxLayout()
        lbl = QLabel("CRUX FLOW v2");
        lbl.setStyleSheet("color:#B0BEC5; font-weight:bold")
        btn = QPushButton(qta.icon('fa5s.times', color="#B0BEC5"), "");
        btn.setFlat(True)
        btn.clicked.connect(self.reject)
        top.addWidget(lbl);
        top.addStretch();
        top.addWidget(btn)
        layout.addLayout(top)

        # Suggestion Bar (Simplified for this demo)
        self.sugg_layout = QHBoxLayout()
        self.sugg_labels = []
        for _ in range(3):
            l = QLabel();
            l.setAlignment(Qt.AlignmentFlag.AlignCenter);
            l.setFont(QFont("Segoe UI", 14))
            self.sugg_layout.addWidget(l);
            self.sugg_labels.append(l)
        layout.addLayout(self.sugg_layout)

        self.display = QLineEdit();
        self.display.setReadOnly(True);
        self.display.setPlaceholderText("Ready...")
        layout.addWidget(self.display)

        grid_widget = QWidget();
        self.grid = QGridLayout(grid_widget);
        self.grid.setSpacing(15)
        self.buttons = {}
        for d, (r, c) in {'UP': (0, 1), 'LEFT': (1, 0), 'RIGHT': (1, 2), 'DOWN': (2, 1)}.items():
            btn = CruxButton();
            self.grid.addWidget(btn, r, c);
            self.buttons[d] = btn

        # Corners
        self.btn_bs = CruxButton();
        self.btn_bs.set_icon('fa5s.backspace')
        self.grid.addWidget(self.btn_bs, 0, 2)
        self.btn_sp = CruxButton();
        self.btn_sp.set_icon('fa5s.minus')  # Space
        self.grid.addWidget(self.btn_sp, 2, 2)

        self.center_hint = QLabel();
        self.center_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_hint.setStyleSheet(f"color:{COLORS['accent']}; font-weight:bold");
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
                    # 进入分页组 (左侧)
                    self.is_paging_group = True
                    self.current_page_idx = 0
                    self.selected_group_data = GROUP_LEFT_PAGES[0]
                else:
                    # 进入普通组
                    self.is_paging_group = False
                    self.selected_group_data = MAIN_MENU[self.active_direction][0]

                self.current_state = self.STATE_GROUP
                self.active_direction = None
        elif cmd == 'BLINK_THREE':
            self.display.setText(self.display.text()[:-1])  # Backspace

        self._refresh_highlight()
        self._refresh_ui()

    def _handle_group(self, cmd):
        if cmd in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
            self.active_direction = cmd
        elif cmd == 'BLINK_TWICE':
            char = self.selected_group_data.get(self.active_direction or 'CENTER')

            if char == '>>':
                # 下一页
                self.current_page_idx = (self.current_page_idx + 1) % len(GROUP_LEFT_PAGES)
                self.selected_group_data = GROUP_LEFT_PAGES[self.current_page_idx]
                self.active_direction = None  # 重置焦点
            elif char == '<<':
                # 回第一页
                self.current_page_idx = 0
                self.selected_group_data = GROUP_LEFT_PAGES[0]
                self.active_direction = None
            elif char:
                self.display.setText(self.display.text() + char)
                self.current_state = self.STATE_HOME
                self.selected_group_data = None
                self.active_direction = None
                self._update_sugg()
        elif cmd == 'BLINK_THREE':
            self.current_state = self.STATE_HOME  # 退回首页

        self._refresh_highlight()
        self._refresh_ui()

    def _refresh_ui(self):
        if self.current_state == self.STATE_HOME:
            self.center_hint.setText("Look Dir\nBlink x2")
            for d, btn in self.buttons.items():
                btn.set_map_content(MAIN_MENU[d][0])
        elif self.current_state == self.STATE_GROUP:
            c = self.selected_group_data.get('CENTER', '')
            self.center_hint.setText(f"Center:\n{c}")
            for d, btn in self.buttons.items():
                btn.set_single_char(self.selected_group_data.get(d, ''))

    def _refresh_highlight(self):
        for d, btn in self.buttons.items(): btn.set_highlight(d == self.active_direction)

    def _update_sugg(self):
        # 简单更新联想词
        txt = self.display.text().split(' ')[-1].lower()
        matches = [w for w in MOCK_DICTIONARY if w.startswith(txt)][:3] if txt else []
        for i, l in enumerate(self.sugg_labels):
            if i < len(matches):
                l.setText(matches[i]); l.show(); l.setStyleSheet(
                    f"background:{COLORS['accent']};color:white;padding:5px;border-radius:5px")
            else:
                l.hide()

    # Mouse Drag
    def mousePressEvent(self, e):
        self.oldPos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        delta = e.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = e.globalPosition().toPoint()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = EyeTypingWidget();
    w.show()


    def k(e):
        m = {Qt.Key.Key_Up: 'UP', Qt.Key.Key_Down: 'DOWN', Qt.Key.Key_Left: 'LEFT', Qt.Key.Key_Right: 'RIGHT',
             Qt.Key.Key_Return: 'BLINK_TWICE', Qt.Key.Key_Backspace: 'BLINK_THREE'}
        if e.key() in m: w.on_prediction_received(m[e.key()])


    w.keyPressEvent = k
    sys.exit(app.exec())