# File: processing/acquisition_controller.py

import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from enum import Enum, auto
import random


class AcquisitionState(Enum):
    IDLE = auto()
    INSTRUCT = auto()
    COUNTDOWN = auto()
    RECORDING = auto()
    REST = auto()


# --- 配置参数 ---
# 倒计时显示的起始数字
COUNTDOWN_START_VALUE = 3
# 倒计时每跳的间隔 (通常为1秒)
COUNTDOWN_INTERVAL = 1000

INSTRUCTION_DURATION = 2000  # 指令显示时间 (稍微加长一点让用户看清)
RECORDING_DURATION = 1500  # 动作录制时间
REST_DURATION = 1500  # 休息时间

# 动作集合
PRIMARY_ACTIONS = ['FIXATION', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'BLINK_TWICE', 'BLINK_THREE']
INTERLEAVED_ACTION = 'BLINK_ONCE'  # 在每个动作间穿插一次眨眼，用于去漂移或作为分隔
TOTAL_TRIALS = 30  # 总试验次数 (包含穿插动作则实际翻倍)


class AcquisitionController(QObject):
    # --- 信号定义 ---
    started = pyqtSignal()
    finished = pyqtSignal()

    # update_state: (StateEnum, Data)
    # Data 可以是指令文本(str)，也可以是倒计时数字(int)，或者录制的动作名(str)
    update_state = pyqtSignal(AcquisitionState, object)

    # 发送给 DataProcessor 的信号
    start_recording_signal = pyqtSignal()
    stop_recording_signal = pyqtSignal()
    add_marker_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_trial_index = -1
        self.is_running = False

        # 专门用于管理定时器引用的列表，防止“僵尸定时器”在停止后继续触发
        self.active_timers = []

        self.trial_list = []

    def _generate_trial_list(self):
        """生成随机化的试验列表，并穿插基准动作"""
        self.trial_list = []
        random_actions = []

        # 1. 生成足够的随机动作
        while len(random_actions) < TOTAL_TRIALS:
            shuffled = PRIMARY_ACTIONS.copy()
            random.shuffle(shuffled)
            random_actions.extend(shuffled)

        # 截断到目标数量
        random_actions = random_actions[:TOTAL_TRIALS]

        # 2. 构建最终列表 (动作 -> 眨眼 -> 动作 -> 眨眼...)
        for action in random_actions:
            self.trial_list.append(action)
            # 穿插动作 (可选，如果不需要可以注释掉下面这行)
            self.trial_list.append(INTERLEAVED_ACTION)

        print(f"AcquisitionController: Generated {len(self.trial_list)} trials.")

    def start(self):
        """启动采集流程"""
        if self.is_running: return

        print("Starting guided acquisition session...")
        self.is_running = True
        self.active_timers.clear()  # 清理旧的（理论上应该是空的）

        self._generate_trial_list()
        self.current_trial_index = -1

        # 1. 通知外部流程开始
        self.started.emit()

        # 2. 通知 DataProcessor 开始写文件
        self.start_recording_signal.emit()
        self.add_marker_signal.emit("GUIDED_SESSION_START")

        # 3. 稍作延迟后开始第一个 Trial
        self._start_timer(1000, self._next_step)

    def stop(self):
        """强制停止采集流程"""
        if not self.is_running: return

        print("Stopping guided acquisition...")
        self.is_running = False

        # --- 核心修复：停止并清理所有待触发的定时器 ---
        for timer in self.active_timers:
            if timer.isActive():
                timer.stop()
        self.active_timers.clear()

        self._finish_acquisition(aborted=True)

    def _start_timer(self, duration, callback):
        """
        【核心辅助函数】
        创建一个受管的单次定时器。这确保了如果在等待期间调用 stop()，
        该回调永远不会被执行，防止崩溃。
        """
        timer = QTimer(self)
        timer.setSingleShot(True)

        # 定义一个闭包来清理 active_timers 列表
        def on_timeout():
            if timer in self.active_timers:
                self.active_timers.remove(timer)
            if self.is_running:  # 双重保险：只有在运行状态下才执行回调
                callback()

        timer.timeout.connect(on_timeout)
        self.active_timers.append(timer)
        timer.start(duration)

    def _next_step(self):
        """进入下一个试验"""
        if not self.is_running: return

        self.current_trial_index += 1

        # 检查是否结束
        if self.current_trial_index >= len(self.trial_list):
            self._finish_acquisition(aborted=False)
            return

        # 开始当前 Trial 的流程：指令 -> 倒计时 -> 录制 -> 休息
        self._show_instruction()

    def _show_instruction(self):
        """阶段 1: 显示指令"""
        action = self.trial_list[self.current_trial_index]

        # 格式化显示文本
        display_text = action.replace('_', ' ').title()
        if action == 'FIXATION':
            display_text = "Relax & Look Straight"
        elif 'BLINK' in action:
            display_text = f"Action: {display_text}"
        else:
            display_text = f"Action: Look {display_text}"

        self.update_state.emit(AcquisitionState.INSTRUCT, display_text)

        # 等待后进入倒计时
        self._start_timer(INSTRUCTION_DURATION, self._start_countdown)

    def _start_countdown(self):
        """阶段 2: 初始化倒计时"""
        if not self.is_running: return
        self.countdown_value = COUNTDOWN_START_VALUE
        self._countdown_tick()

    def _countdown_tick(self):
        """倒计时递归逻辑"""
        if not self.is_running: return

        if self.countdown_value > 0:
            self.update_state.emit(AcquisitionState.COUNTDOWN, self.countdown_value)
            self.countdown_value -= 1
            # 1秒后再次调用自己
            self._start_timer(COUNTDOWN_INTERVAL, self._countdown_tick)
        else:
            # 倒计时结束，开始录制
            self._start_recording_trial()

    def _start_recording_trial(self):
        """阶段 3: 录制动作"""
        if not self.is_running: return

        action = self.trial_list[self.current_trial_index]
        self.update_state.emit(AcquisitionState.RECORDING, action)

        # 添加开始标记
        self.add_marker_signal.emit(f"{action}_START")

        # 定义录制结束后的回调
        def on_recording_end():
            if self.is_running:
                self.add_marker_signal.emit(f"{action}_END")
                self._show_rest()

        # 等待录制时长
        self._start_timer(RECORDING_DURATION, on_recording_end)

    def _show_rest(self):
        """阶段 4: 休息"""
        if not self.is_running: return

        self.update_state.emit(AcquisitionState.REST, "Rest...")

        # 休息结束后，循环回 _next_step
        self._start_timer(REST_DURATION, self._next_step)

    def _finish_acquisition(self, aborted=False):
        """结束采集流程"""
        self.is_running = False  # 确保标志位关闭

        if aborted:
            self.add_marker_signal.emit("GUIDED_SESSION_ABORTED")
            print("Session aborted.")
        else:
            self.add_marker_signal.emit("GUIDED_SESSION_END")
            print("Session finished successfully.")

        # 停止文件录制
        self.stop_recording_signal.emit()

        # 通知 UI 关闭遮罩层
        self.finished.emit()