import socket
from PyQt6.QtCore import QObject, pyqtSignal


class DeviceDiscoveryWorker(QObject):
    """
    负责发送 UDP 广播 'WHO_IS_EEG?' 并等待 'I_AM_EEG_DEVICE' 回复。
    一旦找到，通过 device_found 信号返回 IP 地址。
    """
    device_found = pyqtSignal(str, str)  # 信号: (ip_address, message)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, target_port=3333):
        super().__init__()
        self.target_port = target_port
        self._is_running = True

    def run(self):
        udp_sock = None
        try:
            # 1. 创建 UDP Socket
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 2. 允许发送广播 (关键)
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # 3. 设置超时 (3秒搜不到就停止)
            udp_sock.settimeout(3.0)

            # 绑定到任意本地端口
            udp_sock.bind(('', 0))

            print("Discovery: Sending broadcast WHO_IS_EEG? ...")

            # 4. 发送广播暗号 (必须与下位机一致)
            msg = b"WHO_IS_EEG?"
            # 广播地址 255.255.255.255
            udp_sock.sendto(msg, ('255.255.255.255', self.target_port))

            # 5. 循环接收回复
            while self._is_running:
                try:
                    data, addr = udp_sock.recvfrom(1024)
                    ip_address = addr[0]
                    content = data.decode('utf-8', errors='ignore')

                    # 验证下位机的回复暗号
                    if "I_AM_EEG_DEVICE" in content:
                        print(f"Discovery: Found device at {ip_address}")
                        self.device_found.emit(ip_address, "Device Found")
                        self._is_running = False
                        break

                except socket.timeout:
                    self.error_occurred.emit(
                        "Search timeout. Device not found.\nPlease ensure device is powered on and connected to WiFi.")
                    break
                except Exception as e:
                    self.error_occurred.emit(f"Discovery error: {e}")
                    break

        except Exception as e:
            self.error_occurred.emit(f"Socket setup error: {e}")
        finally:
            if udp_sock:
                udp_sock.close()
            self.finished.emit()

    def stop(self):
        self._is_running = False