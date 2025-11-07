import serial
import serial.tools.list_ports
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 从您的 C 代码中提取的常量
CMD_START = b'START_EEG'
CMD_STOP = b'STOP_EEG'

# 与其他接收器相同的常量
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
#NUM_CHANNELS = 8
# V_REF = 4.5
# GAIN = 24.0
# LSB_TO_UV = (V_REF / GAIN / (2 ** 23 - 1)) * 1e6


class SerialDataReceiver(QObject):
    # --- 信号定义 ---
    connection_status = pyqtSignal(str)
    raw_data_received = pyqtSignal(np.ndarray)

    def __init__(self, port, baudrate, num_channels, frame_size, v_ref, gain):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self._is_running = False
        self.ser = None

        self.num_channels = num_channels
        self.frame_size = frame_size
        self.lsb_to_uv = (v_ref / gain / (2 ** 23 - 1)) * 1e6

        # --- 数据包处理相关的实例属性 ---
        self.num_frames_per_packet = 50  # 默认值，与硬件匹配
        # self.frame_size = 27
        self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
        self.buffer = bytearray()

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        """动态更新每包的帧数和包大小 (为保持接口一致性)"""
        self.num_frames_per_packet = frames
        self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
        print(f"Serial Receiver: Frames per packet set to {self.num_frames_per_packet}")

    def _parse_packet_vectorized(self, payload):
        """这个函数现在完全依赖于实例变量，因此是动态的"""
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))

        # 假设状态字节总是3个
        channel_data = frames[:, 3:]

        # reshape 会根据 self.num_channels 自动调整
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))

        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:,
                                                                                                       :, 2].astype(
            np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000

        # 使用在 __init__ 中计算好的转换因子
        return (raw_vals * self.lsb_to_uv).astype(np.float32).T

    @pyqtSlot()
    def run(self):
        """此槽函数由 QThread 启动，负责串口的完整生命周期"""
        self._is_running = True
        try:
            self.connection_status.emit(f"Opening port {self.port} at {self.baudrate} bps...")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connection_status.emit("Port opened. Sending START command...")

            # 关键：发送启动命令
            self.ser.write(CMD_START)

            self.connection_status.emit(f"Connected to {self.port}. Waiting for data...")

            while self._is_running:
                # 读取所有在缓冲区中的数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.buffer.extend(data)

                # --- 与蓝牙接收器完全相同的缓冲区处理逻辑 ---
                while True:
                    header_index = self.buffer.find(PACKET_HEADER)
                    if header_index == -1:
                        if len(self.buffer) > self.packet_size:
                            print(f"Warning (Serial): Discarding {len(self.buffer)} bytes, no header found.")
                            self.buffer.clear()
                        break

                    if header_index > 0:
                        print(f"Warning (Serial): Discarded {header_index} sync bytes.")
                        del self.buffer[:header_index]

                    if len(self.buffer) < self.packet_size:
                        break

                    raw_packet = self.buffer[:self.packet_size]
                    del self.buffer[:self.packet_size]

                    if raw_packet[:4] == PACKET_HEADER:
                        parsed_data = self._parse_packet_vectorized(raw_packet[4:])
                        self.raw_data_received.emit(parsed_data)
                    else:
                        print("Warning (Serial): Discarded a packet with corrupted header.")

        except serial.SerialException as e:
            self.connection_status.emit(f"Serial Error: {e}")
        finally:
            if self.ser and self.ser.is_open:
                print("Sending STOP command and closing port.")
                self.ser.write(CMD_STOP)
                self.ser.close()
            if self._is_running:  # 只有在非主动停止时才显示“已断开”
                self.connection_status.emit("Serial port disconnected")
            self._is_running = False

    def stop(self):
        """从主线程调用的停止方法"""
        print("Stopping serial receiver...")
        self._is_running = False