import asyncio
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from bleak import BleakClient, BleakScanner

# --- 常量 ---
# 这些值应该与您的STM32设备匹配
NOTIFY_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
# 默认值设为10，与STM32匹配。可以通过Settings菜单更改。
DEFAULT_FRAMES_PER_PACKET = 10
FRAME_SIZE = 27
PACKET_HEADER = b'\xaa\xbb\xcc\xdd'
NUM_CHANNELS = 8
V_REF = 4.5
GAIN = 24.0
LSB_TO_UV = (V_REF / GAIN / (2 ** 23 - 1)) * 1e6


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
        self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
        self.buffer = bytearray()

    # --- 槽函数 ---
    @pyqtSlot(int)
    def set_frames_per_packet(self, frames):
        self.num_frames_per_packet = frames
        self.packet_size = 4 + (self.frame_size * self.num_frames_per_packet)
        print(f"Bluetooth Receiver: Frames per packet set to {self.num_frames_per_packet}")

    # --- 解析函数 ---
    def _parse_packet_vectorized(self, payload):
        frames = np.frombuffer(payload, dtype=np.uint8).reshape((self.num_frames_per_packet, self.frame_size))
        channel_data = frames[:, 3:]
        reshaped_data = channel_data.reshape((self.num_frames_per_packet, self.num_channels, 3))
        b1, b2, b3 = reshaped_data[:, :, 0].astype(np.int32), reshaped_data[:, :, 1].astype(np.int32), reshaped_data[:, :, 2].astype(np.int32)
        raw_vals = (b1 << 16) | (b2 << 8) | b3
        raw_vals[raw_vals >= 0x800000] -= 0x1000000
        return (raw_vals * self.lsb_to_uv).astype(np.float32).T

    # --- 蓝牙核心逻辑 ---
    def _notification_handler(self, sender, data: bytearray):
        """
        当收到蓝牙数据时，此回调函数被 bleak 内部的事件循环调用。
        """
        self.buffer.extend(data)

        # 循环处理缓冲区中所有可能的完整数据包
        while True:
            header_index = self.buffer.find(PACKET_HEADER)
            if header_index == -1:
                # 找不到包头，但可能只收了一部分，保留最后几个字节以备拼接
                if len(self.buffer) > self.packet_size:
                    print(f"Warning (BLE): Discarding {len(self.buffer)} bytes, no header found.")
                    self.buffer.clear()
                break

            if header_index > 0:
                print(f"Warning (BLE): Discarded {header_index} sync bytes.")
                del self.buffer[:header_index]

            if len(self.buffer) < self.packet_size:
                break  # 缓冲区中没有一个完整的包了

            # 提取一个完整的数据包并从缓冲区移除
            raw_packet = self.buffer[:self.packet_size]
            del self.buffer[:self.packet_size]

            if raw_packet[:4] == PACKET_HEADER:
                try:
                    parsed_data = self._parse_packet_vectorized(raw_packet[4:])
                    self.raw_data_received.emit(parsed_data)
                except Exception as e:
                    print(f"Error parsing BLE packet: {e}")
            else:
                print("Warning (BLE): Discarded a packet with corrupted header.")

    @pyqtSlot()
    def run(self):
        """
        此槽函数由 QThread 启动，它负责创建并运行 asyncio 事件循环。
        """
        self._is_running = True
        try:
            # 每个线程都需要自己的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._main_ble_loop())
        except Exception as e:
            print(f"Error in BLE run loop: {e}")
        finally:
            self.connection_status.emit("蓝牙已断开")
            self._is_running = False

    async def _main_ble_loop(self):
        """
        这是主要的异步函数，负责连接、订阅和保持连接。
        """
        self.connection_status.emit(f"正在连接蓝牙设备 {self.address}...")
        try:
            # 使用 async with 来确保连接被正确关闭
            async with BleakClient(self.address, timeout=20.0) as self.client:
                if self.client.is_connected:
                    self.connection_status.emit(f"已连接到 {self.address}")

                    # 订阅特征以接收数据
                    await self.client.start_notify(NOTIFY_CHARACTERISTIC_UUID, self._notification_handler)

                    # 保持连接，直到被外部的 stop() 方法停止
                    while self._is_running and self.client.is_connected:
                        await asyncio.sleep(0.1)  # 短暂休眠以让出CPU

                    # 停止订阅
                    if self.client.is_connected:
                        await self.client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
        except Exception as e:
            self.connection_status.emit(f"蓝牙连接错误: {e}")

    def stop(self):
        """
        从外部（主线程）调用的停止方法。
        """
        self._is_running = False
        print("Stopping BLE receiver...")