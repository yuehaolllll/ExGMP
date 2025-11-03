# In processing/ica_processor.py

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 尝试导入 FastICA，如果失败则给出提示
try:
    from sklearn.decomposition import FastICA
except ImportError:
    print("Error: scikit-learn is not installed. Please install it using 'pip install scikit-learn'")
    FastICA = None


class ICAProcessor(QObject):
    """
    一个在后台线程中运行的处理器，用于训练ICA模型。
    """
    # 信号：当训练完成时发出
    # 参数:
    #   1. object: 训练好的 ica 模型实例
    #   2. np.ndarray: 分解出的独立成分的时间序列数据 (用于可视化)
    training_finished = pyqtSignal(object, np.ndarray)

    # 信号：如果训练过程中发生错误，则发出
    training_failed = pyqtSignal(str)

    @pyqtSlot(np.ndarray)
    def train(self, calibration_data):
        """
        接收校准数据并训练 FastICA 模型。
        这是一个槽函数，可以被主线程的信号调用。
        """
        if FastICA is None:
            self.training_failed.emit("scikit-learn is not installed.")
            return

        # calibration_data 的形状是 (n_channels, n_samples)
        # FastICA 需要的输入形状是 (n_samples, n_features)，所以我们需要转置
        data_for_ica = calibration_data.T

        print(f"ICAProcessor: Starting training on data with shape {data_for_ica.shape}...")

        try:
            # 1. 初始化 FastICA 模型
            # n_components 应该等于通道数
            n_channels = calibration_data.shape[0]
            ica = FastICA(n_components=n_channels,
                          whiten='unit-variance',
                          max_iter=500,  # 增加迭代次数以提高收敛性
                          random_state=0)  # 设置随机种子以保证结果可复现

            # 2. 训练模型并获取独立成分 (sources)
            sources = ica.fit_transform(data_for_ica)

            # 3. 准备可视化数据
            # sources 的形状是 (n_samples, n_components)
            # 为了方便绘图，我们将其转置为 (n_components, n_samples)
            components_for_viz = sources.T

            print("ICAProcessor: Training finished successfully.")

            # 4. 发出完成信号，将模型和成分数据传递回主线程
            self.training_finished.emit(ica, components_for_viz)

        except Exception as e:
            error_message = f"An error occurred during ICA training: {e}"
            print(error_message)
            self.training_failed.emit(error_message)