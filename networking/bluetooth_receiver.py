import asyncio
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from bleak import BleakClient
import struct

# --- 常量 ---
NOTIFY_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
NUM_CHANNELS = 8
V_REF = 4.5
GAIN = 24.0
LSB_TO_UV = (V_REF / GAIN / (2 ** 23 - 1)) * 1e6


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

class BluetoothDataReceiver(QObject):
    # --- 信号定义 ---
    connection_status = pyqtSignal(str)
    raw_data_received = pyqtSignal(np.ndarray)

    def __init__(self, device_address, num_channels, frame_size, v_ref, gain):
        super().__init__()
        self.address = device_address
        self._is_running = False
        self.client = None

        self.num_channels = num_channels
        self.frame_size = frame_size
        self.lsb_to_uv = (v_ref / gain / (2 ** 23 - 1)) * 1e6

        self.num_frames_per_packet = 10  # 蓝牙通常用较小的包

        # 更新数据包大小定义
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_seq_num_size = 4
        self.packet_crc_size = 2
        # 总包大小 = 包头(4) + 序号(4) + 负载 + CRC(2)
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        self.last_sequence_number = -1  # 用于检测丢包

        self.buffer = bytearray()

    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        self.num_frames_per_packet = frames
        # 相应地更新包大小
        self.packet_payload_size = self.frame_size * self.num_frames_per_packet
        self.packet_size = 4 + self.packet_seq_num_size + self.packet_payload_size + self.packet_crc_size
        print(f"Bluetooth Receiver: Frames/packet set to {self.num_frames_per_packet}, new packet size: {self.packet_size}")


    def _parse_packet_vectorized(self, payload):
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
        channel_data = frames[:, 3:]
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))
        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:, :, 2].astype(np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000
        return (raw_vals * self.lsb_to_uv).astype(np.float32).T

    def _notification_handler(self, sender, data: bytearray):
        """
        当收到蓝牙数据时，此回调函数被 bleak 内部的事件循环调用。
        """
        # # --- 调试打印 1: 确认蓝牙数据到达 ---
        # if data:
        #     print(f"DEBUG: BLE received {len(data)} bytes.")

        self.buffer.extend(data)

        while True:
            # --- 调试打印 2: 检查缓冲区状态和包头搜索 ---
            header_index = self.buffer.find(PACKET_HEADER)
            if header_index == -1:
                # 如果缓冲区很大但找不到头，说明数据流可能有问题
                if len(self.buffer) > self.packet_size:
                    print(f"DEBUG WARNING: Buffer has {len(self.buffer)} bytes but NO header found. Clearing.")
                    self.buffer.clear()
                break  # 等待更多数据

            if header_index > 0:
                print(f"DEBUG: Discarded {header_index} sync bytes.")
                del self.buffer[:header_index]

            # --- 调试打印 3: 检查是否有足够数据构成一个完整包 ---
            if len(self.buffer) < self.packet_size:
                # print(f"DEBUG: Buffer has {len(self.buffer)} bytes, waiting for full packet of {self.packet_size}.")
                break  # 等待更多数据

            raw_packet = bytes(self.buffer[:self.packet_size])
            del self.buffer[:self.packet_size]

            try:
                seq_num = struct.unpack('>I', raw_packet[4:8])[0]
                received_crc = struct.unpack('>H', raw_packet[-2:])[0]
            except struct.error:
                print("DEBUG ERROR: Failed to unpack metadata. Packet corrupted or wrong size.")
                continue

            data_to_check = raw_packet[4:-2]
            calculated_crc = crc16_ccitt(data_to_check)

            # --- 调试打印 4: 最关键的CRC校验结果 ---
            if received_crc != calculated_crc:
                print(f"DEBUG CRC MISMATCH on packet #{seq_num}! "
                      f"Expected_CRC: {calculated_crc}, Received_CRC: {received_crc}. Packet dropped.")
                continue  # 丢弃这个损坏的包

            # 如果代码能运行到这里，说明CRC校验通过了
            #print(f"DEBUG: Packet #{seq_num} PASSED CRC check!")

            # ... 后续的丢包检测和数据解析 ...
            if self.last_sequence_number != -1 and seq_num != self.last_sequence_number + 1:
                # ...
                print(f"DEBUG WARNING: Packet loss detected!")
                # ...

            self.last_sequence_number = seq_num
            payload = raw_packet[8:-2]
            parsed_data = self._parse_packet_vectorized(payload)
            self.raw_data_received.emit(parsed_data)


    @pyqtSlot()
    def run(self):
        self._is_running = True
        # 重置包序号计数器
        self.last_sequence_number = -1
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._main_ble_loop())
        except Exception as e:
            print(f"Error in BLE run loop: {e}")
        finally:
            self.connection_status.emit("蓝牙已断开")
            self._is_running = False

    async def _main_ble_loop(self):
        self.connection_status.emit(f"正在连接蓝牙设备 {self.address}...")
        try:
            async with BleakClient(self.address, timeout=20.0) as self.client:
                if self.client.is_connected:
                    self.connection_status.emit(f"已连接到 {self.address}")
                    await self.client.start_notify(NOTIFY_CHARACTERISTIC_UUID, self._notification_handler)
                    while self._is_running and self.client.is_connected:
                        await asyncio.sleep(0.1)
                    if self.client.is_connected:
                        await self.client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
        except Exception as e:
            self.connection_status.emit(f"蓝牙连接错误: {e}")

    def stop(self):
        self._is_running = False
        print("Stopping BLE receiver...")