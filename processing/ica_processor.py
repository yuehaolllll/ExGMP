# In processing/ica_processor.py

import numpy as np
import os
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 尝试导入 MNE，如果失败则给出提示
try:
    import mne

    print("MNE-Python library loaded successfully.")
except ImportError:
    print("Error: MNE-Python is not installed. Please install it using 'pip install mne'")
    mne = None


class ICAProcessor(QObject):
    training_finished = pyqtSignal(object, np.ndarray)
    training_failed = pyqtSignal(str)

    @pyqtSlot(np.ndarray, int, list)
    def train(self, data_chunk, sampling_rate, channel_names):
        """
        使用 MNE-Python 和 AMICA 算法训练ICA模型。
        这是一个槽函数，可以被主线程的信号调用。
        """
        if mne is None:
            self.training_failed.emit("MNE-Python is not installed.")
            return

        # 检查 AMICA 可执行文件的路径是否已设置
        if 'AMICA_PATH' not in os.environ:
            msg = "AMICA executable path not set. Please set it in MainWindow.__init__"
            print(f"[ERROR] {msg}")
            self.training_failed.emit(msg)
            return

        # data_chunk 的形状是 (n_channels, n_samples)
        print(f"ICAProcessor: Starting AMICA training on data with shape {data_chunk.shape}...")

        try:
            # 1. 创建 MNE-Python 需要的 Info 对象 (元数据)
            n_channels = len(channel_names)
            info = mne.create_info(ch_names=channel_names, sfreq=sampling_rate, ch_types='eeg')

            # 2. 将 numpy 数组转换为 MNE 的 RawArray 对象
            # 注意：MNE期望的单位是伏特(V)，而我们的数据是微伏(µV)，所以要除以1,000,000
            raw = mne.io.RawArray(data_chunk / 1e6, info)

            # 3. 初始化 ICA 对象，指定使用 AMICA 方法
            #    fit_params 将被传递给 AMICA 可执行文件
            #    我们采纳论文的建议：进行多次迭代以实现自动样本拒绝
            ica = mne.preprocessing.ICA(
                n_components=n_channels,
                method='amica',
                fit_params=dict(
                    max_iter=2000,  # AMICA 总的最大迭代次数
                    num_models=1,  # 通常使用1个模型
                    auto_reject=True,  # 开启自动拒绝
                    reject_around_mean=True,
                    # 以下参数模拟了论文中 "5-10次迭代，3个标准差" 的建议
                    num_rejects=10,  # 进行10轮样本拒绝
                    reject_sigma=3  # 拒绝阈值为3个标准差
                )
            )

            # 4. 运行 ICA.fit()，这会调用 AMICA 可执行程序
            ica.fit(raw)

            # 5. 获取分解出的独立成分用于可视化
            sources = ica.get_sources(raw)
            components_for_viz = sources.get_data()

            print("ICAProcessor: AMICA training finished successfully.")

            # 6. 发出完成信号，将模型(ica对象)和成分数据传递回主线程
            self.training_finished.emit(ica, components_for_viz)

        except Exception as e:
            error_message = f"An error occurred during AMICA training: {e}"
            print(error_message)
            self.training_failed.emit(error_message)