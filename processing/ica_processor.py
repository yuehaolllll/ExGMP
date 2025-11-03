# In processing/ica_processor.py

import numpy as np
import os
import subprocess
import tempfile
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

# 再次导入MNE，我们仍然需要它来处理数据
try:
    import mne
except ImportError:
    mne = None


class ICAProcessor(QObject):
    training_finished = pyqtSignal(object, np.ndarray)
    training_failed = pyqtSignal(str)

    @pyqtSlot(np.ndarray, int, list)
    def train(self, data_chunk, sampling_rate, channel_names):
        if 'AMICA_PATH' not in os.environ:
            self.training_failed.emit("AMICA executable path not set.")
            return

        amica_path = os.environ['AMICA_PATH']
        n_channels, n_samples = data_chunk.shape

        # 创建一个临时目录来存放AMICA的输入输出文件
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"Created temporary directory for AMICA: {tmpdir}")

            # 1. 准备AMICA的输入数据文件
            # AMICA需要一个float32的二进制文件
            input_data_path = os.path.join(tmpdir, 'eeg_data.fdt')
            # 将我们的numpy数组以float32格式写入文件
            data_chunk.astype(np.float32).tofile(input_data_path)

            # 2. 构建命令行指令
            # 这是最核心的部分，我们手动构建调用amica15.exe的命令
            command = [
                amica_path,
                str(n_channels),  # num_chans
                str(n_samples),  # num_frames
                '1',  # num_models (we use 1)
                str(n_samples),  # max_iter
                '1',  # do_newton
                '1.0',  # lrate
                'outdir', tmpdir  # 指定输出目录
            ]

            print(f"\n--- Running AMICA Command ---")
            print(" ".join(command))
            print("-----------------------------\n")

            try:
                # 3. 执行AMICA程序
                # 我们捕获它的所有输出，以便调试
                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=True,  # 如果AMICA返回错误码，则抛出异常
                    cwd=tmpdir  # 在临时目录中运行
                )

                # 打印AMICA的原始输出
                print("\n--- AMICA Standard Output ---")
                print(process.stdout)
                print("-----------------------------\n")
                if process.stderr:
                    print("\n--- AMICA Standard Error ---")
                    print(process.stderr)
                    print("----------------------------\n")

                # 4. 如果成功，从AMICA的输出文件中加载结果
                # AMICA会将解混矩阵保存为 'W.txt'
                weights_path = os.path.join(tmpdir, 'W.txt')
                unmixing_matrix = np.loadtxt(weights_path).astype(np.float64)

                # AMICA会将球化矩阵保存为 'S.txt'
                sphere_path = os.path.join(tmpdir, 'S.txt')
                sphering_matrix = np.loadtxt(sphere_path).astype(np.float64)

                # 5. 将加载的结果手动应用到 MNE 的 ICA 对象中
                # 这样我们仍然可以利用MNE的后续功能
                info = mne.create_info(ch_names=channel_names, sfreq=sampling_rate, ch_types='eeg')
                raw = mne.io.RawArray(data_chunk / 1e6, info)

                ica = mne.preprocessing.ICA(n_components=n_channels)

                # 手动设置ICA对象的内部矩阵
                ica.info = info
                ica.ch_names = channel_names
                ica.pre_whitener_ = sphering_matrix
                ica.unmixing_matrix_ = unmixing_matrix @ np.linalg.pinv(sphering_matrix)
                ica._update_mixing_matrix()
                ica._update_ica_names()

                # 获取成分用于可视化
                sources = ica.get_sources(raw)
                components_for_viz = sources.get_data()

                print("ICAProcessor: AMICA training finished successfully (manual call).")
                self.training_finished.emit(ica, components_for_viz)

            except subprocess.CalledProcessError as e:
                # 如果AMICA程序运行失败
                error_msg = (
                    f"AMICA executable failed with exit code {e.returncode}.\n\n"
                    f"--- AMICA STDOUT ---\n{e.stdout}\n\n"
                    f"--- AMICA STDERR ---\n{e.stderr}"
                )
                print(error_msg)
                self.training_failed.emit(error_msg)
            except FileNotFoundError:
                # 如果找不到W.txt等输出文件
                error_msg = "AMICA ran but did not produce output files. Check AMICA logs above."
                print(error_msg)
                self.training_failed.emit(error_msg)
            except Exception as e:
                # 其他所有未知错误
                error_msg = f"An unexpected error occurred during manual AMICA call: {e}"
                print(error_msg)
                self.training_failed.emit(error_msg)