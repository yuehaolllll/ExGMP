# In processing/ica_processor.py

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 确保你已经安装了 MNE: pip install mne
try:
    from mne.preprocessing import ICA
    from mne import create_info
    from mne.io import RawArray
except ImportError:
    print("Error: MNE-Python is not installed. Please install it using 'pip install mne'")
    ICA, create_info, RawArray = None, None, None


class ICAProcessor(QObject):
    """
    使用 MNE-Python 的 ICA 在后台线程中训练模型。
    这是一个更健壮、更专业的实现。
    """
    training_finished = pyqtSignal(object, np.ndarray)
    training_failed = pyqtSignal(str)

    # --- 核心修改 1: train 方法现在需要 sampling_rate ---
    @pyqtSlot(np.ndarray, int)
    def train(self, calibration_data, sampling_rate):
        """
        接收校准数据和采样率，并训练 MNE ICA 模型。
        """
        if ICA is None:
            self.training_failed.emit("MNE-Python is not installed.")
            return

        # calibration_data 的形状是 (n_channels, n_samples)
        n_channels, n_samples = calibration_data.shape
        print(f"ICAProcessor (MNE): Starting training on data with shape {calibration_data.shape} at {sampling_rate} Hz...")

        try:
            # 1. 创建 MNE 需要的 `info` 对象
            # MNE 需要知道数据的元信息，比如通道名称和采样率
            ch_names = [f'CH {i + 1}' for i in range(n_channels)]
            info = create_info(ch_names=ch_names, sfreq=sampling_rate, ch_types='eeg')

            # 2. 将 NumPy 数组包装成 MNE 的 RawArray 对象
            raw = RawArray(calibration_data, info)

            # 3. 初始化并训练 MNE ICA 模型
            # 我们使用 picard 算法，它通常比 fastica 更稳定
            # max_iter='auto' 会自动处理收敛问题
            ica = ICA(n_components=n_channels,
                      method='picard',
                      max_iter='auto',
                      random_state=97) # 设置随机种子以保证结果可复现

            ica.fit(raw)

            # 4. 获取独立成分用于可视化
            # ica.get_sources() 返回一个 Raw 对象，我们从中提取数据
            sources_raw = ica.get_sources(raw)
            components_for_viz = sources_raw.get_data()

            print("ICAProcessor (MNE): Training finished successfully.")

            # 5. 发出完成信号，将模型和成分数据传递回主线程
            # 信号的“契约”保持不变，MainWindow 无需知道我们换了引擎
            self.training_finished.emit(ica, components_for_viz)

        except Exception as e:
            error_message = f"An error occurred during MNE ICA training: {e}"
            print(error_message)
            self.training_failed.emit(error_message)