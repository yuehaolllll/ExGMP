# File: processing/ica_processor.py

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

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
    【修复版】：增加了降采样和自适应成分数量，解决 4000Hz 下的协方差矩阵病态问题。
    """
    training_finished = pyqtSignal(object, np.ndarray, list)
    training_failed = pyqtSignal(str)

    @pyqtSlot(np.ndarray, int)
    def train(self, calibration_data, sampling_rate):
        """
        接收校准数据和采样率，并训练 MNE ICA 模型。
        """
        if ICA is None:
            self.training_failed.emit("MNE-Python is not installed.")
            return

        n_channels, n_samples = calibration_data.shape
        print(f"ICAProcessor: Received {n_samples} samples @ {sampling_rate}Hz.")

        if n_channels < 3:
            self.training_failed.emit(
                f"Error: At least 3 channels required (2 EOG + EEG). Got {n_channels}.")
            return

        try:
            # --- 1. 定义通道配置 ---
            ch_names = [f'CH {i + 1}' for i in range(n_channels)]
            ch_types = ['eeg'] * n_channels

            # 硬编码前两个为 EOG
            ch_types[0] = 'eog';
            ch_names[0] = 'EOG_V'
            ch_types[1] = 'eog';
            ch_names[1] = 'EOG_H'

            # --- 2. 创建 Raw 对象 ---
            info = create_info(ch_names=ch_names, sfreq=sampling_rate, ch_types=ch_types)
            # 转换为 Volts
            raw = RawArray(calibration_data * 1e-6, info)

            # --- [关键修复 1] 降采样 ---
            # ICA 不需要 4000Hz 的精度，200Hz 足够捕捉眨眼和伪迹
            # 这能极大提高计算速度，并规避高频噪音导致的矩阵不稳定
            TARGET_ICA_FREQ = 200
            if sampling_rate > TARGET_ICA_FREQ:
                print(f"Info: Resampling data from {sampling_rate}Hz to {TARGET_ICA_FREQ}Hz for ICA stability...")
                raw.resample(TARGET_ICA_FREQ, npad="auto")

            # --- 3. 预处理滤波 ---
            # 1Hz 高通是 ICA 的标配，去漂移
            raw.filter(l_freq=1.0, h_freq=None, verbose=False)

            # --- [关键修复 2] 自适应成分数量 ---
            # 不要硬编码 n_components = n_eeg_channels。
            # 使用 float (0.99) 让算法保留解释 99% 方差的主成分。
            # 如果矩阵病态，它会自动减少成分数量（例如从 6 降到 5），从而避免崩溃。

            print("Info: Fitting ICA using extended-infomax (or fastica)...")
            ica = ICA(
                n_components=0.99,  # <--- 这里的改动解决了 RuntimeWarning
                method='fastica',  # fastica 通常比 picard 更稳健
                max_iter=500,  # 增加最大迭代次数
                random_state=97
            )

            # 训练 (仅使用 EEG 通道，剔除 EOG)
            ica.fit(raw, verbose=True)

            # --- 4. 自动检测 EOG 伪迹 ---
            print("Info: Detecting EOG artifacts...")
            # threshold 3.0 是经验值，如果觉得太敏感可以调高到 4.0
            suggested_bad_indices, scores = ica.find_bads_eog(raw, threshold=3.0, verbose=False)

            # 确保索引是简单的 int 列表
            suggested_bad_indices = [int(x) for x in suggested_bad_indices]
            print(f"Info: MNE suggested artifacts indices: {suggested_bad_indices}")

            # --- 5. 获取源数据用于绘图 ---
            sources = ica.get_sources(raw).get_data()

            print(f"ICAProcessor: Training finished. Decomposed into {sources.shape[0]} components.")
            self.training_finished.emit(ica, sources, suggested_bad_indices)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.training_failed.emit(f"ICA Training Error: {str(e)}")