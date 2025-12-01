import socket
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# --- 配置常量 ---
PORT = 3333
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'


class DataReceiver(QObject):
    connection_status = pyqtSignal(str)
    raw_data_received = pyqtSignal(np.ndarray)

    def __init__(self, target_ip, num_channels, v_ref, gain):
        """
        :param target_ip: 必须传入明确的 IP (由 Discovery 模块找到的)
        """
        super().__init__()
        self.target_ip = target_ip

        self.tcp_sock = None  # 用于发送 Config/Start/Stop
        self.udp_sock = None  # 用于接收高速数据流

        self._is_running = False

        self.active_channels = num_channels
        self.v_ref = v_ref
        self.gain = gain

        self.lsb_to_uv = np.float32(0.0)
        self._recalculate_conversion_factor()

        self.num_frames_per_packet = 50

        # 包结构参数初始化
        self.packet_size = 0
        self.frame_size = 0
        self.packet_payload_size = 0
        self._update_packet_size()

        self.last_sequence_number = -1

    def _recalculate_conversion_factor(self):
        if self.gain != 0:
            val = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6
            self.lsb_to_uv = np.float32(val)
        else:
            self.lsb_to_uv = np.float32(0.0)

    @pyqtSlot(int)
    def update_active_channels(self, active_channel_count):
        self.active_channels = active_channel_count
        self._update_packet_size()

    def _update_packet_size(self):
        # 帧: 3 Status + N * 3 Data
        self.frame_size = 3 + self.active_channels * 3
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        # 包: Header(4) + Seq(4) + Payload + CRC(2)
        self.packet_size = 4 + 4 + self.packet_payload_size + 2

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        if self.num_frames_per_packet == frames: return
        self.num_frames_per_packet = frames
        self._update_packet_size()

    @pyqtSlot(float)
    def set_gain(self, new_gain):
        if self.gain != new_gain:
            self.gain = new_gain
            self._recalculate_conversion_factor()

    def _parse_packet_vectorized(self, raw_bytes):
        """解析 UDP 包负载 (NumPy 加速版)"""
        try:
            # 1. 零拷贝视图
            data_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            # 2. Reshape
            frames = data_arr.reshape((self.num_frames_per_packet, self.frame_size))
            # 3. 提取通道数据 (跳过前3字节 status)
            channel_data = frames[:, 3:]
            # 4. Reshape
            reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.active_channels, 3))
            # 5. 合成 24-bit Int
            b1 = reshaped_data[:, :, 0].astype(np.int32)
            b2 = reshaped_data[:, :, 1].astype(np.int32)
            b3 = reshaped_data[:, :, 2].astype(np.int32)
            raw_vals = (b1 << 16) | (b2 << 8) | b3
            # 6. 符号位扩展
            mask = (raw_vals & 0x800000) != 0
            raw_vals[mask] -= 0x1000000
            # 7. 转微伏 (Channels, Frames)
            return (raw_vals * self.lsb_to_uv).astype(np.float32).T
        except Exception as e:
            print(f"Parse Error: {e}")
            return np.zeros((self.active_channels, 0), dtype=np.float32)

    @pyqtSlot()
    def run(self):
        """混合架构主循环"""
        self._is_running = True
        self.last_sequence_number = -1

        try:
            # --- 1. TCP 连接 (控制链路) ---
            self.connection_status.emit(f"Connecting Control to {self.target_ip}...")

            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.settimeout(3.0)
            self.tcp_sock.connect((self.target_ip, PORT))

            # 开启 Keepalive
            self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            self.connection_status.emit(f"Connected to {self.target_ip}. Waiting for data...")

            # --- 2. UDP 监听 (数据链路) ---
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)  # 8MB Buffer
            self.udp_sock.bind(('0.0.0.0', PORT))  # 监听本地 3333
            self.udp_sock.settimeout(1.0)  # 读取超时，用于响应 stop

            print(f"UDP Listener started on port {PORT}")

            # --- 3. 接收循环 ---
            while self._is_running:
                try:
                    # 接收 UDP 包 (最大 2048 字节)
                    data, addr = self.udp_sock.recvfrom(2048)

                    # 简单校验
                    if len(data) != self.packet_size: continue
                    if data[0:4] != PACKET_HEADER: continue

                    # 提取序号 (Big Endian)
                    seq_num = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]

                    # 丢包/乱序检测 (仅打印，不中断)
                    if self.last_sequence_number != -1:
                        diff = seq_num - self.last_sequence_number
                        if diff != 1 and not (self.last_sequence_number > 0xFFFFFF00 and seq_num < 100):
                            pass  # print(f"UDP Loss/Order: {diff}")

                    self.last_sequence_number = seq_num

                    # 解析 Payload (去除 Header=8, CRC=2)
                    payload_bytes = data[8:-2]
                    parsed_data = self._parse_packet_vectorized(payload_bytes)
                    self.raw_data_received.emit(parsed_data)

                except socket.timeout:
                    continue  # 超时重试，检查 _is_running
                except Exception as e:
                    print(f"UDP Recv Error: {e}")

        except Exception as e:
            self.connection_status.emit(f"Connection Failed: {e}")
        finally:
            self.stop()

    def send_command(self, command_bytes):
        """通过 TCP 发送 Config/Start/Stop"""
        if self.tcp_sock and self._is_running:
            try:
                self.tcp_sock.sendall(command_bytes)
            except Exception as e:
                print(f"Command send error: {e}")
                self.connection_status.emit("Control Link Broken")

    def stop(self):
        self._is_running = False
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except:
                pass
            self.udp_sock = None
        if self.tcp_sock:
            try:
                self.tcp_sock.close()
            except:
                pass
            self.tcp_sock = None
        self.connection_status.emit("Disconnected")