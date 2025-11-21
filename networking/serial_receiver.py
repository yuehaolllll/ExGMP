# File: networking/serial_receiver.py

import serial
import serial.tools.list_ports
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import struct

# --- 常量 ---
CMD_START = b'START_EEG'
CMD_STOP = b'STOP_EEG'
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
MAX_BUFFER_SIZE = 1024 * 1024  # 1MB 缓冲上限

# CRC16-CCITT (0x1021) 查表法优化
_crc_table = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
    0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
    0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
    0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
    0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
    0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
    0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
    0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
    0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
    0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
    0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
    0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
    0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
    0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
    0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
    0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
    0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
    0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
    0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
    0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
    0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
    0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
    0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
]


def crc16_ccitt_fast(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        index = ((crc >> 8) ^ byte) & 0xFF
        crc = ((crc << 8) ^ _crc_table[index]) & 0xFFFF
    return crc


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
        self.active_channels = num_channels
        self.lsb_to_uv = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6

        self.num_frames_per_packet = 50

        # 初始化包大小计算
        self.packet_size = 0
        self.frame_size = 0
        self._update_packet_size()

        self.last_sequence_number = -1
        self.buffer = bytearray()

    def _update_packet_size(self):
        # 每帧 = 3字节Header(Status) + N * 3字节Data
        self.frame_size = 3 + self.active_channels * 3

        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_seq_num_size = 4
        self.packet_crc_size = 2
        # Header(4) + Seq(4) + Payload + CRC(2)
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        print(f"SerialReceiver: Packet size recalculated: {self.packet_size} bytes")

    @pyqtSlot(int)
    def update_active_channels(self, num_channels):
        """当活跃通道数改变时更新内部状态"""
        print(f"SerialReceiver: Updating active channels to {num_channels}")
        self.active_channels = num_channels
        self._update_packet_size()

    @pyqtSlot(float)
    def set_gain(self, new_gain):
        if self.gain != new_gain:
            print(f"SerialReceiver: Updating gain to x{new_gain}")
            self.gain = new_gain
            self.lsb_to_uv = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        if self.num_frames_per_packet == frames: return
        self.num_frames_per_packet = frames
        self._update_packet_size()
        print(f"Serial Receiver: Frames/packet set to {frames}")

    def _parse_packet_vectorized(self, payload):
        try:
            frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
            channel_data = frames[:, 3:]

            # 使用 active_channels
            reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.active_channels, 3))

            b1 = reshaped_data[:, :, 0].astype(np.int32)
            b2 = reshaped_data[:, :, 1].astype(np.int32)
            b3 = reshaped_data[:, :, 2].astype(np.int32)

            raw_vals = (b1 << 16) | (b2 << 8) | b3
            raw_vals[raw_vals >= 0x800000] -= 0x1000000

            return (raw_vals * self.lsb_to_uv).astype(np.float32).T

        except ValueError as e:
            print(f"Serial Parse Error: {e}")
            return np.zeros((self.active_channels, 0))

    @pyqtSlot()
    def run(self):
        self._is_running = True
        self.last_sequence_number = -1
        self.buffer.clear()

        try:
            self.connection_status.emit(f"Opening {self.port} @ {self.baudrate}...")
            # timeout=0.1 非阻塞读取，防止卡死在 read
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)

            # 清空硬件缓冲区，防止积压的旧数据干扰
            self.ser.reset_input_buffer()

            self.connection_status.emit("Port opened. Sending START...")
            self.ser.write(CMD_START)
            self.connection_status.emit(f"Connected: {self.port}")

            while self._is_running:
                if self.ser.in_waiting > 0:
                    # 一次最多读 4KB，防止单次读取过大
                    data = self.ser.read(min(self.ser.in_waiting, 4096))
                    self.buffer.extend(data)

                # 缓冲区保护
                if len(self.buffer) > MAX_BUFFER_SIZE:
                    print("Serial Buffer overflow! Clearing.")
                    self.buffer.clear()
                    continue

                while True:
                    header_index = self.buffer.find(PACKET_HEADER)
                    if header_index == -1:
                        break

                    if header_index > 0:
                        del self.buffer[:header_index]

                    if len(self.buffer) < self.packet_size:
                        break

                    raw_packet = bytes(self.buffer[:self.packet_size])
                    del self.buffer[:self.packet_size]

                    try:
                        seq_num = struct.unpack('>I', raw_packet[4:8])[0]
                        received_crc = struct.unpack('>H', raw_packet[-2:])[0]
                    except struct.error:
                        continue

                    data_to_check = raw_packet[4:-2]
                    calculated_crc = crc16_ccitt_fast(data_to_check)

                    if received_crc != calculated_crc:
                        print(f"CRC Error: Pkt {seq_num}")
                        continue

                    if self.last_sequence_number != -1:
                        diff = seq_num - self.last_sequence_number
                        if diff != 1:
                            if not (self.last_sequence_number > 0xFFFFFF00 and seq_num < 100):
                                print(f"Lost {diff - 1} packets")

                    self.last_sequence_number = seq_num

                    payload = raw_packet[8:-2]
                    parsed_data = self._parse_packet_vectorized(payload)
                    self.raw_data_received.emit(parsed_data)

        except serial.SerialException as e:
            self.connection_status.emit(f"Serial Error: {e}")
        finally:
            if self.ser and self.ser.is_open:
                try:
                    print("Sending STOP...")
                    self.ser.write(CMD_STOP)
                    self.ser.close()
                except:
                    pass

            if self._is_running:
                self.connection_status.emit("Disconnected")
            self._is_running = False

    def stop(self):
        print("Stopping serial receiver...")
        self._is_running = False