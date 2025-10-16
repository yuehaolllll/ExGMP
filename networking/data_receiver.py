import socket
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# --- 常量 ---
HOST = '192.168.4.1'
PORT = 3333
NUM_CHANNELS = 8
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
V_REF = 4.5
GAIN = 24.0
LSB_TO_UV = (V_REF / GAIN / (2**23 - 1)) * 1e6

class DataReceiver(QObject):
    connection_status = pyqtSignal(str)
    raw_data_received = pyqtSignal(np.ndarray) # 发射原始解析数据

    def __init__(self):
        super().__init__()
        self.sock = None
        self._is_running = False
        self.num_frames_per_packet = 50  # 默认值
        self.packet_size = 4 + (27 * self.num_frames_per_packet)

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        """动态更新每包的帧数和包大小"""
        self.num_frames_per_packet = frames
        # 这里的 27 是每个通道的数据字节数，与 __init__ 中保持一致
        self.packet_size = 4 + (27 * self.num_frames_per_packet)
        print(f"WiFi Receiver: Frames per packet set to {self.num_frames_per_packet}")

    def _recv_all(self, n):
        buffer = bytearray()
        while len(buffer) < n:
            packet = self.sock.recv(n - len(buffer))
            if not packet: return None
            buffer.extend(packet)
        return buffer

    def _parse_packet_vectorized(self, payload):
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, 27))
        channel_data = frames[:, 3:]
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, NUM_CHANNELS, 3))
        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:, :, 2].astype(np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000
        return (raw_vals * LSB_TO_UV).astype(np.float32).T

    @pyqtSlot()
    def run(self):
        self._is_running = True
        buffer = bytearray()
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

                    # --- 最终的、稳健的处理循环 ---
                    while True:
                        # 1. 寻找包头
                        header_index = buffer.find(PACKET_HEADER)
                        if header_index == -1:
                            # 找不到包头，但可能只收了一部分，保留最后几个字节
                            if len(buffer) > self.packet_size:
                                print(f"Warning: Discarding {len(buffer)} bytes, no header found.")
                                buffer.clear()
                            break  # 退出内层循环，等待更多数据

                        # 2. 丢弃包头前的垃圾数据
                        if header_index > 0:
                            print(f"Warning: Discarded {header_index} sync bytes.")
                            del buffer[:header_index]

                        # 3. 检查是否有足够的数据构成一个完整的包
                        if len(buffer) < self.packet_size:
                            break  # 退出内层循环，等待更多数据

                        # 4. 提取并处理
                        raw_packet = buffer[:self.packet_size]
                        del buffer[:self.packet_size]  # 从缓冲区中移除这个包

                        # 5. 只处理包头正确的包
                        if raw_packet[:4] == PACKET_HEADER:
                            parsed_data = self._parse_packet_vectorized(raw_packet[4:])
                            self.raw_data_received.emit(parsed_data)
                        else:
                            # 如果提取出的包包头又不对了，说明流中出现了错误
                            # 我们已经删除了这个坏包，循环会继续寻找下一个好包
                            print("Warning: Discarded a packet with corrupted header.")

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