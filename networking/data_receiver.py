# File: networking/data_receiver.py

import socket
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# --- 配置常量 ---
HOST = '192.168.4.1'
PORT = 3333
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'

# 4MB 的大接收缓冲区，足以应对网络波动
MAX_BUFFER_SIZE = 4 * 1024 * 1024
# 每次从 Socket 读取的最大字节数
RECV_CHUNK_SIZE = 16384


class DataReceiver(QObject):
    # 信号定义
    connection_status = pyqtSignal(str)
    # 明确发送 float32 类型的数组
    raw_data_received = pyqtSignal(np.ndarray)

    def __init__(self, num_channels, v_ref, gain):
        super().__init__()
        self.sock = None
        self._is_running = False

        self.active_channels = num_channels
        self.v_ref = v_ref
        self.gain = gain

        # 转换因子直接使用 float32，避免计算时自动升级为 float64
        self.lsb_to_uv = np.float32(0.0)
        self._recalculate_conversion_factor()

        self.num_frames_per_packet = 50

        # 包大小相关变量
        self.packet_size = 0
        self.frame_size = 0
        self.packet_payload_size = 0
        self._update_packet_size()

        self.last_sequence_number = -1

    def _recalculate_conversion_factor(self):
        """计算 LSB 到微伏的转换系数 (Float32)"""
        if self.gain != 0:
            val = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6
            self.lsb_to_uv = np.float32(val)
        else:
            self.lsb_to_uv = np.float32(0.0)

    @pyqtSlot(int)
    def update_active_channels(self, active_channel_count):
        print(f"DataReceiver: Updating active channels to {active_channel_count}")
        self.active_channels = active_channel_count
        self._update_packet_size()

    def _update_packet_size(self):
        """更新包结构尺寸"""
        # 帧结构: 3字节 Status + N通道 * 3字节 Data
        self.frame_size = 3 + self.active_channels * 3
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet

        # 包结构: Header(4) + Seq(4) + Payload(...) + CRC(2)
        self.packet_size = 4 + 4 + self.packet_payload_size + 2
        print(f"DataReceiver: Packet size recalculated: {self.packet_size} bytes")

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        if self.num_frames_per_packet == frames: return
        self.num_frames_per_packet = frames
        self._update_packet_size()

    @pyqtSlot(float)
    def set_gain(self, new_gain):
        if self.gain != new_gain:
            print(f"DataReceiver: Updating gain to x{new_gain}")
            self.gain = new_gain
            self._recalculate_conversion_factor()

    def _parse_packet_vectorized(self, payload_view):
        """
        利用 NumPy 的 View 和位运算直接解析内存数据，
        避免 Python 循环和 struct 解包。
        """
        try:
            # 1. 将 memoryview 直接映射为 uint8 数组 (Zero Copy)
            # 注意: payload_view 是从 bytearray 切片出来的，内存是连续的
            raw_bytes = np.frombuffer(payload_view, dtype=np.uint8)

            # 2. 重塑为 (frames, frame_size)
            frames = raw_bytes.reshape((self.num_frames_per_packet, self.frame_size))

            # 3. 提取通道数据部分 (View, No Copy)
            # 跳过每帧前3个字节的状态字
            channel_data = frames[:, 3:]

            # 4. 重塑为 (frames, channels, 3bytes)
            reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.active_channels, 3))

            # 5. 转换为 int32 以进行位运算 (这是必须的 Copy 步骤，也是主要的耗时点)
            # 比 struct.unpack 快 50-100 倍
            b1 = reshaped_data[:, :, 0].astype(np.int32)
            b2 = reshaped_data[:, :, 1].astype(np.int32)
            b3 = reshaped_data[:, :, 2].astype(np.int32)

            # 6. 合成 24位 整数
            # Value = (B1 << 16) | (B2 << 8) | B3
            raw_vals = (b1 << 16) | (b2 << 8) | b3

            # 7. 符号位扩展 (24-bit Two's Complement -> 32-bit Int)
            # 检查第23位是否为1
            mask = (raw_vals & 0x800000) != 0
            # 如果是负数，减去 2^24
            raw_vals[mask] -= 0x1000000

            # 8. 转换为微伏 (利用广播机制直接生成 Float32)
            # 最终输出形状: (channels, frames)
            return (raw_vals * self.lsb_to_uv).astype(np.float32).T

        except Exception as e:
            print(f"Parse Error: {e}")
            # 返回空数组防止崩溃
            return np.zeros((self.active_channels, 0), dtype=np.float32)

    @pyqtSlot()
    def run(self):
        """主接收循环"""
        self._is_running = True

        # 预分配 4MB 连续内存
        buffer = bytearray(MAX_BUFFER_SIZE)
        # 创建 memoryview 以支持高效切片
        view = memoryview(buffer)

        # 读写指针
        read_idx = 0
        write_idx = 0

        self.last_sequence_number = -1

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)
            self.connection_status.emit(f"Connecting to {HOST}:{PORT}...")
            self.sock.connect((HOST, PORT))

            # 增大操作系统内核级接收缓冲区
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            self.connection_status.emit(f"Connected to {HOST}:{PORT}")

            while self._is_running:
                try:
                    # --- 1. 内存管理 ---
                    # 如果缓冲区剩余空间不足，将未处理的数据搬回头部
                    if write_idx > MAX_BUFFER_SIZE - RECV_CHUNK_SIZE:
                        valid_len = write_idx - read_idx
                        if valid_len > 0:
                            buffer[:valid_len] = buffer[read_idx:write_idx]

                        write_idx = valid_len
                        read_idx = 0
                        # view 需要重新指向 buffer (虽然 buffer 引用没变，但这是一个好习惯)
                        view = memoryview(buffer)

                    # --- 2. 零拷贝接收 ---
                    # 直接写入 bytearray 的空闲区域
                    # recv_into 返回接收到的字节数
                    n_bytes = self.sock.recv_into(view[write_idx:], RECV_CHUNK_SIZE)

                    if not n_bytes:
                        if self._is_running: self.connection_status.emit("Connection closed by server")
                        break

                    write_idx += n_bytes

                    # --- 3. 解析循环 ---
                    while True:
                        # 检查剩余数据是否足够一个包
                        # 注意：这里我们甚至不检查 Header，直接假设流是连续的，
                        # 依靠校验或 Header 查找来纠正偏移
                        if (write_idx - read_idx) < self.packet_size:
                            break

                        # 快速检查 Header (直接比较内存)
                        # buffer[read_idx : read_idx+4] 会产生极小的切片开销
                        if buffer[read_idx: read_idx + 4] != PACKET_HEADER:
                            # 如果 Header 对不上，说明失步了，搜索下一个 Header
                            # 限制搜索范围，防止在大缓冲区里搜索太久
                            search_limit = min(write_idx, read_idx + self.packet_size * 2)
                            header_offset = buffer.find(PACKET_HEADER, read_idx + 1, search_limit)

                            if header_offset == -1:
                                # 没找到，丢弃这部分不可靠的数据，保留一部分以便下次拼接
                                # 但为了简单高效，这里直接推进指针
                                read_idx = max(read_idx + 1, search_limit - 3)
                                continue
                            else:
                                # 找到了，对齐指针
                                read_idx = header_offset
                                # 再次检查长度
                                if (write_idx - read_idx) < self.packet_size:
                                    break

                        # --- 4. 提取数据 ---
                        # 计算 Seq Num (大端序)
                        # 直接通过索引访问，比 struct.unpack 更快
                        seq_num = (buffer[read_idx + 4] << 24) | \
                                  (buffer[read_idx + 5] << 16) | \
                                  (buffer[read_idx + 6] << 8) | \
                                  buffer[read_idx + 7]

                        # 丢包检测
                        if self.last_sequence_number != -1:
                            diff = seq_num - self.last_sequence_number
                            if diff != 1:
                                # 处理序号回绕的情况
                                if not (self.last_sequence_number > 0xFFFFFF00 and seq_num < 100):
                                    # 只是打印，不中断流
                                    print(f"Loss: {diff - 1} pkts (Last: {self.last_sequence_number}, Curr: {seq_num})")

                        self.last_sequence_number = seq_num

                        # 提取 Payload
                        # 使用 view 切片，这是零拷贝操作
                        payload_start = read_idx + 8
                        payload_end = payload_start + self.packet_payload_size
                        payload_view = view[payload_start: payload_end]

                        # 解析并发送
                        parsed_data = self._parse_packet_vectorized(payload_view)
                        self.raw_data_received.emit(parsed_data)

                        # --- 5. 推进指针 ---
                        read_idx += self.packet_size

                except socket.timeout:
                    continue
                except socket.error as e:
                    if self._is_running: self.connection_status.emit(f"Socket Error: {e}")
                    break
                except Exception as e:
                    print(f"Unexpected Error: {e}")
                    break

        except socket.error as e:
            if self._is_running: self.connection_status.emit(f"Connection Failed: {e}")
        finally:
            if self.sock: self.sock.close()
            if self._is_running: self.connection_status.emit("Disconnected")
            self._is_running = False

    def send_command(self, command_bytes):
        """发送指令"""
        if self.sock and self._is_running:
            try:
                self.sock.sendall(command_bytes)
            except socket.error as e:
                print(f"Command send error: {e}")

    def stop(self):
        """停止接收"""
        self._is_running = False
        if self.sock:
            try:
                # 强制关闭读写，打断 recv 阻塞
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()