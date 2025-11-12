# import socket
# import numpy as np
# from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
#
# # --- 常量 ---
# HOST = '192.168.4.1'
# PORT = 3333
# NUM_CHANNELS = 8
# PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
# V_REF = 4.5
# GAIN = 12.0
# LSB_TO_UV = (V_REF / GAIN / (2**23 - 1)) * 1e6
#
# class DataReceiver(QObject):
#     connection_status = pyqtSignal(str)
#     raw_data_received = pyqtSignal(np.ndarray) # 发射原始解析数据
#
#     def __init__(self, num_channels, frame_size, v_ref, gain):
#         super().__init__()
#         self.sock = None
#         self._is_running = False
#         self.num_channels = num_channels
#         self.frame_size = frame_size
#         self.lsb_to_uv = (v_ref / gain / (2 ** 23 - 1)) * 1e6
#
#         self.num_frames_per_packet = 50
#         self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
#
#     @pyqtSlot(int)
#     def set_frames_per_packet(self, frames):
#         self.num_frames_per_packet = frames
#         self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
#         print(f"WiFi Receiver: Frames per packet set to {self.num_frames_per_packet}")
#
#     def _recv_all(self, n):
#         buffer = bytearray()
#         while len(buffer) < n:
#             packet = self.sock.recv(n - len(buffer))
#             if not packet: return None
#             buffer.extend(packet)
#         return buffer
#
#     def _parse_packet_vectorized(self, payload): # <-- 核心修改
#         frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
#         channel_data = frames[:, 3:]
#         reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))
#         b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:, :, 2].astype(np.int32)
#         raw_vals = (b1 << 16) | (b2 << 8) | b3
#         raw_vals[raw_vals >= 0x800000] -= 0x1000000
#         return (raw_vals * self.lsb_to_uv).astype(np.float32).T
#
#     @pyqtSlot()
#     def run(self):
#         self._is_running = True
#         buffer = bytearray()
#         try:
#             self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             self.sock.settimeout(1.0)
#             self.connection_status.emit(f"正在连接 {HOST}:{PORT}...")
#             self.sock.connect((HOST, PORT))
#             self.connection_status.emit(f"已连接到 {HOST}:{PORT}")
#
#             while self._is_running:
#                 try:
#                     data = self.sock.recv(4096)
#                     if not data:
#                         if self._is_running: self.connection_status.emit("连接已断开")
#                         break
#                     buffer.extend(data)
#
#                     # --- 最终的、稳健的处理循环 ---
#                     while True:
#                         # 1. 寻找包头
#                         header_index = buffer.find(PACKET_HEADER)
#                         if header_index == -1:
#                             # 找不到包头，但可能只收了一部分，保留最后几个字节
#                             if len(buffer) > self.packet_size:
#                                 print(f"Warning: Discarding {len(buffer)} bytes, no header found.")
#                                 buffer.clear()
#                             break  # 退出内层循环，等待更多数据
#
#                         # 2. 丢弃包头前的垃圾数据
#                         if header_index > 0:
#                             print(f"Warning: Discarded {header_index} sync bytes.")
#                             del buffer[:header_index]
#
#                         # 3. 检查是否有足够的数据构成一个完整的包
#                         if len(buffer) < self.packet_size:
#                             break  # 退出内层循环，等待更多数据
#
#                         # 4. 提取并处理
#                         raw_packet = buffer[:self.packet_size]
#                         del buffer[:self.packet_size]  # 从缓冲区中移除这个包
#
#                         # 5. 只处理包头正确的包
#                         if raw_packet[:4] == PACKET_HEADER:
#                             parsed_data = self._parse_packet_vectorized(raw_packet[4:])
#                             self.raw_data_received.emit(parsed_data)
#                         else:
#                             # 如果提取出的包包头又不对了，说明流中出现了错误
#                             # 我们已经删除了这个坏包，循环会继续寻找下一个好包
#                             print("Warning: Discarded a packet with corrupted header.")
#
#                 except socket.timeout:
#                     continue
#                 except socket.error as e:
#                     if self._is_running: self.connection_status.emit(f"连接错误: {e}")
#                     break
#
#         except socket.error as e:
#             if self._is_running: self.connection_status.emit(f"连接错误: {e}")
#         finally:
#             if self.sock: self.sock.close()
#             if self._is_running: self.connection_status.emit("已断开")
#             self._is_running = False
#
#     def stop(self):
#         self._is_running = False
#         if self.sock: self.sock.close()

import socket
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import struct  # --- 修改开始 ---：导入struct模块用于解包

# --- 常量 ---
HOST = '192.168.4.1'
PORT = 3333
NUM_CHANNELS = 8
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
V_REF = 4.5
GAIN = 12.0
LSB_TO_UV = (V_REF / GAIN / (2 ** 23 - 1)) * 1e6


# --- 修改开始 ---：添加CRC16计算函数
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


# --- 修改结束 ---

class DataReceiver(QObject):
    connection_status = pyqtSignal(str)
    raw_data_received = pyqtSignal(np.ndarray)
    stream_discontinuity_detected = pyqtSignal()

    def __init__(self, num_channels, frame_size, v_ref, gain):
        super().__init__()
        self.sock = None
        self._is_running = False
        self.num_channels = num_channels
        self.frame_size = frame_size
        self.lsb_to_uv = (v_ref / gain / (2 ** 23 - 1)) * 1e6

        self.num_frames_per_packet = 50

        # --- 修改开始 ---: 更新数据包大小定义
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet  # 1350 bytes
        self.packet_seq_num_size = 4
        self.packet_crc_size = 2
        # 总包大小 = 包头(4) + 序号(4) + 负载(1350) + CRC(2) = 1360 bytes
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size

        self.last_sequence_number = -1  # 用于检测丢包
        # --- 修改结束 ---

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        """ 注意：如果此功能仍需使用，它现在会影响包大小，需谨慎 """
        self.num_frames_per_packet = frames
        # --- 修改开始 ---: 相应地更新包大小
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        # --- 修改结束 ---
        print(f"WiFi Receiver: Frames/packet set to {self.num_frames_per_packet}, new packet size: {self.packet_size}")

    def _recv_all(self, n):
        buffer = bytearray()
        while len(buffer) < n:
            packet = self.sock.recv(n - len(buffer))
            if not packet: return None
            buffer.extend(packet)
        return buffer

    def _parse_packet_vectorized(self, payload):
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
        channel_data = frames[:, 3:]
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))
        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:,
                                                                                                       :, 2].astype(
            np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000
        return (raw_vals * self.lsb_to_uv).astype(np.float32).T

    @pyqtSlot()
    def run(self):
        self._is_running = True
        buffer = bytearray()

        # --- 修改开始 ---: 重置包序号计数器
        self.last_sequence_number = -1
        # --- 修改结束 ---

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1.0)
            self.connection_status.emit(f"正在连接 {HOST}:{PORT}...")
            self.sock.connect((HOST, PORT))
            self.connection_status.emit(f"已连接到 {HOST}:{PORT}")

            while self._is_running:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        if self._is_running: self.connection_status.emit("连接已断开")
                        break
                    buffer.extend(data)

                    while True:
                        header_index = buffer.find(PACKET_HEADER)
                        if header_index == -1:
                            if len(buffer) > self.packet_size:
                                print(f"Warning: Discarding {len(buffer)} bytes, no header found.")
                                buffer.clear()
                            break

                        if header_index > 0:
                            print(f"Warning: Discarded {header_index} sync bytes.")
                            del buffer[:header_index]

                        if len(buffer) < self.packet_size:
                            break

                        raw_packet = bytes(buffer[:self.packet_size])
                        del buffer[:self.packet_size]

                        # --- 修改开始: 核心校验逻辑 ---

                        # 1. 解包: 提取元数据
                        # '>I' 表示大端(网络字节序)的4字节无符号整数 (包序号)
                        # '>H' 表示大端(网络字节序)的2字节无符号整数 (CRC)
                        try:
                            seq_num = struct.unpack('>I', raw_packet[4:8])[0]
                            received_crc = struct.unpack('>H', raw_packet[-2:])[0]
                        except struct.error:
                            print("Error: Failed to unpack metadata. Corrupted packet.")
                            continue

                        # 2. 校验CRC
                        # CRC的计算范围是 [包序号] + [数据负载]
                        data_to_check = raw_packet[4:-2]
                        calculated_crc = crc16_ccitt(data_to_check)

                        if received_crc != calculated_crc:
                            print(f"[ERROR] CRC mismatch on packet {seq_num}! "
                                  f"Received: {received_crc}, Calculated: {calculated_crc}. Packet is corrupted.")
                            continue  # 丢弃这个损坏的包

                        # 3. 校验包序号 (检测丢包)
                        if self.last_sequence_number != -1 and seq_num != self.last_sequence_number + 1:
                            packets_lost = seq_num - (self.last_sequence_number + 1)
                            print(f"[WARNING] Packet loss detected! "
                                  f"Expected packet {self.last_sequence_number + 1}, but got {seq_num}. "
                                  f"Lost {packets_lost} packet(s).")
                            self.stream_discontinuity_detected.emit()

                        # 更新序号，为下一次检查做准备
                        self.last_sequence_number = seq_num

                        # 4. 提取有效数据负载 (Payload)
                        # 负载位于 [包序号] 之后 和 [CRC] 之前
                        payload = raw_packet[8:-2]

                        # 5. 解析并发送数据 (只有在所有校验通过后才执行)
                        parsed_data = self._parse_packet_vectorized(payload)
                        self.raw_data_received.emit(parsed_data)

                        # --- 修改结束 ---

                except socket.timeout:
                    continue
                except socket.error as e:
                    if self._is_running: self.connection_status.emit(f"连接错误: {e}")
                    break

        except socket.error as e:
            if self._is_running: self.connection_status.emit(f"连接错误: {e}")
        finally:
            if self.sock: self.sock.close()
            if self._is_running: self.connection_status.emit("已断开")
            self._is_running = False

    def stop(self):
        self._is_running = False
        if self.sock: self.sock.close()