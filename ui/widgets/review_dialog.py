# # File: ui/widgets/review_dialog.py
#
# from PyQt6.QtWidgets import QDialog, QVBoxLayout, QSplitter
# from PyQt6.QtCore import Qt
# from PyQt6.QtGui import QGuiApplication
# from .time_domain_widget import TimeDomainWidget
# from .frequency_domain_widget import FrequencyDomainWidget
#
#
# class ReviewDialog(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("File Review")
#
#         # --- 改进 1: 设置窗口标志，使其拥有最大化/最小化按钮 ---
#         # Qt.WindowType.Window 使其表现得像一个独立的子窗口，而不是模态对话框
#         self.setWindowFlags(Qt.WindowType.Window)
#
#         # --- 改进 2: 屏幕自适应尺寸与居中 ---
#         self._resize_to_screen()
#
#         # 创建绘图控件 (显式传入 None 以表明是回放模式)
#         self.time_domain_widget = TimeDomainWidget(data_processor=None)
#         self.frequency_domain_widget = FrequencyDomainWidget()
#
#         # --- 改进 3: 使用 QSplitter 替代简单的 QVBoxLayout ---
#         # 允许用户上下拖动调整时域图和频域图的高度比例
#         layout = QVBoxLayout(self)
#         layout.setContentsMargins(0, 0, 0, 0)  # 移除边缘留白，让图表铺满
#
#         splitter = QSplitter(Qt.Orientation.Vertical)
#         splitter.addWidget(self.time_domain_widget)
#         splitter.addWidget(self.frequency_domain_widget)
#
#         # 设置默认比例：时域图占 70%，频域图占 30%
#         splitter.setSizes([800, 200])
#
#         layout.addWidget(splitter)
#
#     def _resize_to_screen(self):
#         """
#         根据当前屏幕分辨率，将窗口调整为可用区域的 85% 大小并居中。
#         """
#         screen = QGuiApplication.primaryScreen()
#         if not screen:
#             self.resize(1200, 800)  # 后备尺寸
#             return
#
#         # 获取可用几何区域（排除了任务栏等）
#         available_geometry = screen.availableGeometry()
#         screen_w = available_geometry.width()
#         screen_h = available_geometry.height()
#
#         # 计算目标尺寸 (85%)
#         target_w = int(screen_w * 0.85)
#         target_h = int(screen_h * 0.85)
#
#         self.resize(target_w, target_h)
#
#         # 计算居中位置
#         new_x = available_geometry.x() + (screen_w - target_w) // 2
#         new_y = available_geometry.y() + (screen_h - target_h) // 2
#
#         self.move(new_x, new_y)
#
#     def load_and_display(self, result_dict):
#         """
#         Public method to populate the plots with data from a loaded file.
#         """
#         if 'error' in result_dict:
#             self.setWindowTitle(f"Error Loading File: {result_dict['error']}")
#             return
#
#         channel_names = result_dict.get('channels')
#
#         # 1. 显示时域数据
#         self.time_domain_widget.display_static_data(
#             result_dict['data'],
#             result_dict['sampling_rate'],
#             result_dict.get('markers'),  # Use .get() for safety
#             channel_names
#         )
#
#         # 2. 显示频域数据
#         self.frequency_domain_widget.display_static_fft(
#             result_dict['freqs'],
#             result_dict['mags'],
#             channel_names
#         )
#
#         # 3. 更新标题并显示窗口
#         # 获取纯文件名（去掉路径）
#         filename = result_dict.get('filename', 'Unknown File')
#         self.setWindowTitle(f"Reviewing: {filename}")
#
#         # 显示窗口（如果希望直接最大化，可以改用 self.showMaximized()）
#         self.show()


# File: ui/widgets/review_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QSplitter, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QIcon
from .time_domain_widget import TimeDomainWidget
from .frequency_domain_widget import FrequencyDomainWidget


class ReviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Review")

        # --- 窗口属性设置 ---
        # 使其具有最大化/最小化按钮，且像独立窗口一样操作
        self.setWindowFlags(Qt.WindowType.Window)

        # 初始化尺寸
        self._resize_to_screen()

        # --- 初始化子控件 ---
        # 传入 None 表示这是静态回放，不绑定 DataProcessor
        self.time_domain_widget = TimeDomainWidget(data_processor=None)
        self.frequency_domain_widget = FrequencyDomainWidget()

        # --- 布局优化 ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 无边距模式，让波形铺满

        # 使用 QSplitter 允许上下拖动调整高度
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # 设置 Splitter 样式，增加把手的可见度（可选）
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E0E0E0;
                height: 4px;
            }
            QSplitter::handle:hover {
                background-color: #1A73E8;
            }
        """)

        self.splitter.addWidget(self.time_domain_widget)
        self.splitter.addWidget(self.frequency_domain_widget)

        # 设置默认高度比例：时域图占 70%，频域图占 30%
        # 注意：这只是初始建议，用户调整窗口大小时会重新计算
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)

        layout.addWidget(self.splitter)

    def _resize_to_screen(self):
        """屏幕自适应：占据屏幕 85% 大小并居中"""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.resize(1200, 800)
            return

        geom = screen.availableGeometry()
        w, h = geom.width(), geom.height()

        target_w = int(w * 0.85)
        target_h = int(h * 0.85)

        # 居中计算
        x = geom.x() + (w - target_w) // 2
        y = geom.y() + (h - target_h) // 2

        self.resize(target_w, target_h)
        self.move(x, y)

    def load_and_display(self, result_dict):
        """
        加载并显示数据，同时修复频域图显示不全的问题。
        """
        if 'error' in result_dict:
            self.setWindowTitle(f"Error Loading File: {result_dict['error']}")
            return

        channel_names = result_dict.get('channels')
        sampling_rate = result_dict.get('sampling_rate', 1000)

        # --- 1. 时域数据显示 ---
        self.time_domain_widget.display_static_data(
            result_dict['data'],
            sampling_rate,
            result_dict.get('markers'),
            channel_names
        )

        # --- 2. 频域数据显示 (核心修复) ---
        freqs = result_dict['freqs']
        mags = result_dict['mags']

        self.frequency_domain_widget.display_static_fft(
            freqs,
            mags,
            channel_names
        )

        # 【核心修复逻辑】
        # 获取频域图内部的 PlotItem 对象
        fft_plot_item = self.frequency_domain_widget.plot

        # A. 解锁鼠标交互：回放模式下，允许用户缩放 X 轴和 Y 轴查看细节
        fft_plot_item.getViewBox().setMouseEnabled(x=True, y=True)

        # B. 强制自动缩放：确保所有数据都在视野内
        fft_plot_item.autoRange()

        # C. (可选) 优化初始视角：
        # 虽然 autoRange 会显示全貌，但 EEG 高频通常没多少信息。
        # 我们可以将初始视角设定在 0-100Hz (最常用的脑电频段)，但允许用户由缩放查看更多。
        # 如果你想看完整的 FFT (0 - 采样率/2)，请注释掉下面这行 setXRange。
        fft_plot_item.setXRange(0, 100)

        # --- 3. 更新窗口标题 ---
        filename = result_dict.get('filename', 'Unknown File')
        self.setWindowTitle(f"Reviewing: {filename}  |  Fs: {sampling_rate}Hz  |  Channels: {len(channel_names)}")

        self.show()