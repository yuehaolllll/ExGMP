import serial
import serial.tools.list_ports
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import struct # 导入struct模块

# --- 常量 ---
CMD_START = b'START_EEG'
CMD_STOP = b'STOP_EEG'
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'

# 添加CRC16计算函数
def crc16_ccitt(data: bytes) -> int:
    """
    计算CRC16-CCITT校验和，与ESP32固件中的算法保持一致。
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
    return crc & 0xFFFF

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

        self.v_ref = v_ref
        self.gain = gain
        self.num_channels = num_channels
        self.frame_size = frame_size
        self.lsb_to_uv = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6

        self.num_frames_per_packet = 50

        # 更新数据包大小定义
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_seq_num_size = 4
        self.packet_crc_size = 2
        # 总包大小 = 包头(4) + 序号(4) + 负载 + CRC(2)
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        self.last_sequence_number = -1  # 用于检测丢包

        self.buffer = bytearray()

    @pyqtSlot(float)
    def set_gain(self, new_gain):
        """
        一个槽函数，用于从外部更新增益值并重新计算转换系数。
        """
        if self.gain != new_gain:
            print(f"BluetoothDataReceiver: Updating gain to x{new_gain}")
            self.gain = new_gain
            # 重新计算转换系数
            self.lsb_to_uv = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        self.num_frames_per_packet = frames
        # 相应地更新包大小
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        print(f"Serial Receiver: Frames/packet set to {self.num_frames_per_packet}, new packet size: {self.packet_size}")

    def _parse_packet_vectorized(self, payload):
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
        channel_data = frames[:, 3:]
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))
        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:, :, 2].astype(np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000
        return (raw_vals * self.lsb_to_uv).astype(np.float32).T

    @pyqtSlot()
    def run(self):
        self._is_running = True
        # 重置包序号计数器
        self.last_sequence_number = -1
        try:
            self.connection_status.emit(f"Opening port {self.port} at {self.baudrate} bps...")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connection_status.emit("Port opened. Sending START command...")
            self.ser.write(CMD_START)
            self.connection_status.emit(f"Connected to {self.port}. Waiting for data...")

            while self._is_running:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.buffer.extend(data)

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

                    # 核心校验逻
                    raw_packet = bytes(self.buffer[:self.packet_size])
                    del self.buffer[:self.packet_size]

                    # 1. 解包元数据
                    try:
                        seq_num = struct.unpack('>I', raw_packet[4:8])[0]
                        received_crc = struct.unpack('>H', raw_packet[-2:])[0]
                    except struct.error:
                        print("Error (Serial): Failed to unpack metadata. Corrupted packet.")
                        continue

                    # 2. 校验CRC
                    data_to_check = raw_packet[4:-2]
                    calculated_crc = crc16_ccitt(data_to_check)

                    if received_crc != calculated_crc:
                        print(f"[ERROR] (Serial) CRC mismatch on packet {seq_num}! "
                              f"Received: {received_crc}, Calculated: {calculated_crc}. Packet corrupted.")
                        continue

                    # 3. 校验包序号
                    if self.last_sequence_number != -1 and seq_num != self.last_sequence_number + 1:
                        packets_lost = seq_num - (self.last_sequence_number + 1)
                        print(f"[WARNING] (Serial) Packet loss detected! "
                              f"Expected {self.last_sequence_number + 1}, got {seq_num}. "
                              f"Lost {packets_lost} packet(s).")
                        self.stream_discontinuity_detected.emit()

                    self.last_sequence_number = seq_num

                    # 4. 提取有效数据负载
                    payload = raw_packet[8:-2]

                    # 5. 解析并发送数据
                    try:
                        parsed_data = self._parse_packet_vectorized(payload)
                        self.raw_data_received.emit(parsed_data)
                    except Exception as e:
                        print(f"Error parsing Serial packet payload: {e}")

        except serial.SerialException as e:
            self.connection_status.emit(f"Serial Error: {e}")
        finally:
            if self.ser and self.ser.is_open:
                print("Sending STOP command and closing port.")
                self.ser.write(CMD_STOP)
                self.ser.close()
            if self._is_running:
                self.connection_status.emit("Serial port disconnected")
            self._is_running = False

    def stop(self):
        print("Stopping serial receiver...")
        self._is_running = False