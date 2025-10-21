import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QSequentialAnimationGroup, QPropertyAnimation, QPoint, \
    QEasingCurve
from enum import Enum, auto


class AcquisitionState(Enum):
    IDLE = auto()
    INSTRUCT = auto()
    COUNTDOWN = auto()
    RECORDING = auto()
    REST = auto()


# 动作序列
ACTION_SEQUENCE = [
    'FIXATION',
    'UP', 'BLINK',
    'DOWN', 'BLINK',
    'LEFT', 'BLINK',
    'RIGHT', 'BLINK'
]
# 每个阶段的持续时间（毫秒）
INSTRUCTION_DURATION = 1000
COUNTDOWN_DURATION = 1000
RECORDING_DURATION = 3000
REST_DURATION = 3000


class AcquisitionController(QObject):
    # --- 信号：发给UI和DataProcessor的指令 ---
    started = pyqtSignal()
    finished = pyqtSignal()
    # (状态, 附加数据)，例如 (INSTRUCT, "向上看") 或 (COUNTDOWN, 3)
    update_state = pyqtSignal(AcquisitionState, object)

    # --- 信号：发给DataProcessor的录制指令 ---
    start_recording_signal = pyqtSignal()
    stop_recording_signal = pyqtSignal()
    add_marker_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_action_index = -1
        self.is_running = False
        self.active_timers = []

    def start(self):
        """开始完整的引导式采集流程"""
        if self.is_running:
            print("Acquisition is already running.")
            return

        print("Starting guided acquisition...")
        self.is_running = True
        self.current_action_index = -1

        # 发送信号，通知UI采集已开始
        self.started.emit()

        # 触发一次性的“开始录制”指令
        self.start_recording_signal.emit()
        self.add_marker_signal.emit("GUIDED_ACQUISITION_START")

        # 延迟一小会后开始第一个步骤
        QTimer.singleShot(500, self._next_step)

    def stop(self):
        """立即中止采集流程"""
        if not self.is_running:
            return

        print("Aborting guided acquisition...")
        self.is_running = False

        # 停止所有正在等待的定时器
        for timer in self.active_timers:
            timer.stop()
        self.active_timers.clear()

        # 使用 _finish_acquisition 来完成收尾工作
        self._finish_acquisition()

    def _start_timer(self, duration, callback):
        """一个辅助函数，用于创建、存储和启动定时器"""
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.timeout.connect(lambda: self.active_timers.remove(timer) if timer in self.active_timers else None)
        timer.start(duration)
        self.active_timers.append(timer)

    def _next_step(self):
        """状态机的核心，决定并执行下一个步骤"""
        if not self.is_running:
            return

        self.current_action_index += 1

        # 检查是否所有动作都已完成
        if self.current_action_index >= len(ACTION_SEQUENCE):
            self._finish_acquisition()
            return

        # 按“指令 -> 倒计时 -> 录制 -> 休息”的顺序执行
        self._show_instruction()

    def _show_instruction(self):
        action = ACTION_SEQUENCE[self.current_action_index]
        instruction_text = action.replace('_', ' ').title()
        if action == 'FIXATION':
            instruction_text = "Calibration: Please Look Straight Ahead"
        elif action == 'BLINK':
            instruction_text = "Please Blink Normally"
        else:
            instruction_text = f"Look {instruction_text}"

        self.update_state.emit(AcquisitionState.INSTRUCT, instruction_text)
        QTimer.singleShot(INSTRUCTION_DURATION, self._start_countdown)

    def _start_countdown(self):
        if not self.is_running: return
        self.countdown_value = 3
        self._countdown_tick()

    def _countdown_tick(self):
        if self.countdown_value > 0:
            self.update_state.emit(AcquisitionState.COUNTDOWN, self.countdown_value)
            self.countdown_value -= 1
            QTimer.singleShot(1000, self._countdown_tick)
        else:
            self._start_recording_trial()

    def _start_recording_trial(self):
        action = ACTION_SEQUENCE[self.current_action_index]
        self.update_state.emit(AcquisitionState.RECORDING, action)

        # 在每个10秒试验的开始和结束点添加精确的标记
        self.add_marker_signal.emit(f"{action}_START")
        QTimer.singleShot(RECORDING_DURATION, lambda: self.add_marker_signal.emit(f"{action}_END"))

        # 10秒后进入休息阶段
        QTimer.singleShot(RECORDING_DURATION, self._show_rest)

    def _show_rest(self):
        self.update_state.emit(AcquisitionState.REST, "Rest... Look Straight Ahead")
        QTimer.singleShot(REST_DURATION, self._next_step)

    def _finish_acquisition(self):
        print("Guided acquisition finished.")
        self.is_running = False
        self.add_marker_signal.emit("GUIDED_ACQUISITION_END")

        # 触发一次性的“停止录制”指令
        self.stop_recording_signal.emit()

        # 通知UI采集已结束
        self.finished.emit()