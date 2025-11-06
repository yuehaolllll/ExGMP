# In processing/ica_processor.py

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 确保你已经安装了 MNE: pip install mne
try:
    from mne.preprocessing import ICA
    from mne import create_info
    from mne.io import RawArray
    from mne.preprocessing.eog import create_eog_epochs
    #from mne.preprocessing.eog import find_bads_eog
except ImportError:
    print("Error: MNE-Python is not installed. Please install it using 'pip install mne'")
    ICA, create_info, RawArray = None, None, None


class ICAProcessor(QObject):
    """
    使用 MNE-Python 的 ICA 在后台线程中训练模型。
    这是一个更健壮、更专业的实现。
    """
    training_finished = pyqtSignal(object, np.ndarray, list)
    training_failed = pyqtSignal(str)

    # --- 核心修改 1: train 方法现在需要 sampling_rate ---
    @pyqtSlot(np.ndarray, int)
    def train(self, calibration_data, sampling_rate):
        """
        接收校准数据和采样率，并训练 MNE ICA 模型。
        此版本硬编码地将前两个通道 (CH1, CH2) 设置为 EOG 通道。
        """
        if ICA is None:
            self.training_failed.emit("MNE-Python is not installed.")
            return

        n_channels, n_samples = calibration_data.shape
        print(f"ICAProcessor: Starting training. Hard-coding CH1 and CH2 as EOG channels.")

        # --- 检查通道数是否足够 ---
        if n_channels < 3:
            self.training_failed.emit(
                f"Error: At least 3 channels are required for ICA with 2 EOG channels, but got {n_channels}.")
            return

        try:
            # --- 2. 动态生成通道名称和类型，固定前两个为EOG ---
            ch_names = [f'CH {i + 1}' for i in range(n_channels)]
            ch_types = ['eeg'] * n_channels  # 先全部设为 'eeg'

            # 将前两个通道的类型和名称设置为EOG
            ch_types[0] = 'eog'
            ch_types[1] = 'eog'
            ch_names[0] = 'EOG_V'  # V for Vertical
            ch_names[1] = 'EOG_H'  # H for Horizontal

            print(f"Info: Channel types set to: {ch_types}")

            info = create_info(ch_names=ch_names, sfreq=sampling_rate, ch_types=ch_types)
            raw = RawArray(calibration_data, info)

            print("Info: High-pass filtering data at 1.0 Hz for better ICA performance...")
            raw.filter(l_freq=1.0, h_freq=None)

            # --- 3. ICA拟合 ---
            # 计算EEG通道的数量，这对于设置 n_components 至关重要
            n_eeg_channels = ch_types.count('eeg')
            ica = ICA(n_components=n_eeg_channels,  # 成分数应等于EEG通道数
                      method='picard',
                      max_iter='auto',
                      random_state=97)
            # MNE的fit会自动选择`picks='eeg'`来训练，排除EOG通道
            ica.fit(raw)

            # --- 4. 自动检测EOG伪迹 ---
            # MNE的 find_bads_eog 非常智能，它会自动找到所有类型为 'eog' 的通道
            # 并用它们来共同寻找相关的ICA成分。
            # 现在，我们调用 ica 对象自带的 find_bads_eog 方法
            print("Info: Automatically detecting EOG artifacts using all defined EOG channels...")
            suggested_bad_indices, scores = ica.find_bads_eog(raw)

            print(f"Info: MNE suggested components {suggested_bad_indices} as EOG artifacts.")

            # --- 5. 准备数据并发送信号 (逻辑不变) ---
            sources_raw = ica.get_sources(raw)
            # 确保只提取与EEG通道数相匹配的成分进行可视化
            components_for_viz = sources_raw.get_data()

            print("ICAProcessor (MNE): Training finished successfully.")
            self.training_finished.emit(ica, components_for_viz, suggested_bad_indices)

        except Exception as e:
            error_message = f"An error occurred during MNE ICA training: {e}"
            print(error_message)
            self.training_failed.emit(error_message)