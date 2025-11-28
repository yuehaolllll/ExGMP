# File: networking/bluetooth_receiver.py

import asyncio
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from bleak import BleakClient

# --- 常量 ---
NOTIFY_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'

# 预分配 256KB 缓冲区 (足够容纳数秒的积压数据)
MAX_BUFFER_SIZE = 256 * 1024
# 触发内存整理的阈值 (当 buffer 用了一半时)
COMPACT_THRESHOLD = MAX_BUFFER_SIZE // 2

# CRC16-CCITT (0x1021) Table
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


def crc16_ccitt_fast(data: memoryview) -> int:
    """查表法 CRC 计算，兼容 memoryview"""
    crc = 0xFFFF
    for byte in data:
        index = ((crc >> 8) ^ byte) & 0xFF
        crc = ((crc << 8) ^ _crc_table[index]) & 0xFFFF
    return crc


class BluetoothDataReceiver(QObject):
    connection_status = pyqtSignal(str)
    # 明确发送 float32 信号
    raw_data_received = pyqtSignal(np.ndarray)

    def __init__(self, device_address, num_channels, frame_size, v_ref, gain):
        super().__init__()
        self.address = device_address
        self._is_running = False
        self.client = None

        self.v_ref = v_ref
        self.gain = gain
        self.num_channels = num_channels
        self.frame_size = frame_size

        # Float32 转换系数
        self.lsb_to_uv = np.float32(0.0)
        self._recalc_conversion()

        self.num_frames_per_packet = 10

        # 包结构
        self.packet_seq_num_size = 4
        self.packet_crc_size = 2
        self._recalc_packet_size()

        # 预分配内存池
        self.recv_buffer = bytearray(MAX_BUFFER_SIZE)
        # memoryview 允许我们零拷贝地操作 bytearray
        self.view = memoryview(self.recv_buffer)

        self.read_idx = 0
        self.write_idx = 0

        self.last_sequence_number = -1

    def _recalc_conversion(self):
        if self.gain != 0:
            val = (self.v_ref / self.gain / (2 ** 23 - 1)) * 1e6
            self.lsb_to_uv = np.float32(val)
        else:
            self.lsb_to_uv = np.float32(0.0)

    def _recalc_packet_size(self):
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size

    @pyqtSlot(int)
    def update_active_channels(self, num_channels):
        self.num_channels = num_channels
        self.frame_size = 3 + (self.num_channels * 3)
        self._recalc_packet_size()
        print(f"BLE: Channels updated to {num_channels}, PktSize: {self.packet_size}")

    @pyqtSlot(float)
    def set_gain(self, new_gain):
        if self.gain != new_gain:
            self.gain = new_gain
            self._recalc_conversion()

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        if self.num_frames_per_packet == frames: return
        self.num_frames_per_packet = frames
        self._recalc_packet_size()

    def _parse_packet_vectorized(self, payload_view):
        """
        解析函数
        输入 payload_view 是一个 memoryview，无拷贝。
        """
        try:
            # 1. 直接从 View 创建 Numpy 数组 (Zero Copy)
            raw_bytes = np.frombuffer(payload_view, dtype=np.uint8)

            # 2. Reshape
            frames = raw_bytes.reshape((self.num_frames_per_packet, self.frame_size))
            channel_data = frames[:, 3:]
            reshaped = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))

            # 3. 转换为 int32 以进行位运算 (Copy)
            b1 = reshaped[:, :, 0].astype(np.int32)
            b2 = reshaped[:, :, 1].astype(np.int32)
            b3 = reshaped[:, :, 2].astype(np.int32)

            # 4. 24-bit 组合
            raw_vals = (b1 << 16) | (b2 << 8) | b3

            # 5. 补码处理 (符号位扩展)
            mask = (raw_vals & 0x800000) != 0
            raw_vals[mask] -= 0x1000000

            # 6. 转微伏 (Float32)
            return (raw_vals * self.lsb_to_uv).astype(np.float32).T

        except Exception as e:
            print(f"BLE Parse Error: {e}")
            return np.zeros((self.num_channels, 0), dtype=np.float32)

    def _notification_handler(self, sender, data: bytearray):
        """
        Bleak 回调函数。
        这里必须极快，不能阻塞。
        """
        data_len = len(data)

        # 1. 检查缓冲区空间，如果不足或需要整理，进行内存移动
        if self.write_idx + data_len > MAX_BUFFER_SIZE:
            # 计算有效数据长度
            valid_len = self.write_idx - self.read_idx

            # 如果即使整理后也装不下（极少见），或者数据本身就太大了
            if valid_len + data_len > MAX_BUFFER_SIZE:
                print("BLE Buffer Overflow! Resetting.")
                self.write_idx = 0
                self.read_idx = 0
            else:
                # 内存整理：将有效数据搬回头部
                self.recv_buffer[:valid_len] = self.recv_buffer[self.read_idx: self.write_idx]
                self.write_idx = valid_len
                self.read_idx = 0
                # 重置 view 引用
                self.view = memoryview(self.recv_buffer)

        # 2. 写入数据 (Copy from bleak data to our pre-allocated buffer)
        self.recv_buffer[self.write_idx: self.write_idx + data_len] = data
        self.write_idx += data_len

        # 3. 解析循环
        while True:
            # 剩余数据是否足够一个包
            if (self.write_idx - self.read_idx) < self.packet_size:
                break

            # 快速检查 Header
            if self.recv_buffer[self.read_idx: self.read_idx + 4] != PACKET_HEADER:
                # 失步处理：寻找下一个 Header
                # 限制搜索范围，防止卡死
                search_limit = min(self.write_idx, self.read_idx + self.packet_size * 2)
                header_offset = self.recv_buffer.find(PACKET_HEADER, self.read_idx + 1, search_limit)

                if header_offset == -1:
                    # 没找到，丢弃这部分数据
                    self.read_idx = max(self.read_idx + 1, search_limit - 3)
                    continue
                else:
                    self.read_idx = header_offset
                    # 重新检查长度
                    if (self.write_idx - self.read_idx) < self.packet_size:
                        break

            # --- 提取 Header 信息 ---
            # Seq Num (Big Endian)
            seq_num = (self.recv_buffer[self.read_idx + 4] << 24) | \
                      (self.recv_buffer[self.read_idx + 5] << 16) | \
                      (self.recv_buffer[self.read_idx + 6] << 8) | \
                      self.recv_buffer[self.read_idx + 7]

            # Received CRC (Big Endian)
            crc_idx = self.read_idx + self.packet_size - 2
            received_crc = (self.recv_buffer[crc_idx] << 8) | self.recv_buffer[crc_idx + 1]

            # --- CRC 校验 ---
            # 获取需要校验的数据切片 (Payload + Header部分)
            # 范围: [Header(4) + Seq(4) + Payload(...)]，不包含最后的 CRC(2)
            check_view = self.view[self.read_idx + 4: crc_idx]

            calculated_crc = crc16_ccitt_fast(check_view)

            if received_crc != calculated_crc:
                print(f"CRC Err: #{seq_num}")
                # CRC 错误，丢弃整个包，向前滑动 1 字节尝试重新对齐
                # 或者直接跳过 packet_size? 通常跳过整个包更安全
                self.read_idx += self.packet_size
                continue

            # --- 丢包检测 ---
            if self.last_sequence_number != -1:
                diff = seq_num - self.last_sequence_number
                if diff != 1:
                    if not (self.last_sequence_number > 0xFFFFFF00 and seq_num < 100):
                        # print(f"Loss: {diff - 1} pkts") # 减少打印以免阻塞
                        pass
            self.last_sequence_number = seq_num

            # --- 解析 Payload ---
            # 范围: Header(4) + Seq(4) [Start: +8] ... [End: -2] CRC(2)
            payload_view = self.view[self.read_idx + 8: crc_idx]

            parsed_data = self._parse_packet_vectorized(payload_view)
            self.raw_data_received.emit(parsed_data)

            # --- 推进指针 ---
            self.read_idx += self.packet_size

    @pyqtSlot()
    def run(self):
        self._is_running = True
        self.last_sequence_number = -1

        # 重置 Buffer 状态
        self.read_idx = 0
        self.write_idx = 0
        self.recv_buffer = bytearray(MAX_BUFFER_SIZE)
        self.view = memoryview(self.recv_buffer)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._main_ble_loop())
            loop.close()
        except Exception as e:
            print(f"BLE Run Error: {e}")
        finally:
            self.connection_status.emit("Disconnected")
            self._is_running = False

    async def _main_ble_loop(self):
        self.connection_status.emit(f"Connecting to {self.address}...")
        try:
            async with BleakClient(self.address, timeout=15.0) as self.client:
                if self.client.is_connected:
                    self.connection_status.emit(f"Connected: {self.address}")

                    # 订阅通知
                    await self.client.start_notify(NOTIFY_CHARACTERISTIC_UUID, self._notification_handler)

                    # 保持连接
                    while self._is_running and self.client.is_connected:
                        await asyncio.sleep(0.2)  # 稍微增加 sleep 时间减少 CPU 占用

                    if self.client.is_connected:
                        await self.client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
        except Exception as e:
            self.connection_status.emit(f"BLE Error: {str(e)}")

    def stop(self):
        self._is_running = False
        print("BluetoothReceiver: Stopping...")