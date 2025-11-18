import os
import shutil
import sys

# 我们要处理的目标文件夹，从命令行参数获取
# 例如：python cleanup_for_release.py F:\temp_release\app_release
target_dir = sys.argv[1]

print(f"--- Cleaning up project in: {target_dir} ---")

for root, dirs, files in os.walk(target_dir, topdown=False):
    # 1. 处理 __pycache__ 文件夹
    if os.path.basename(root) == '__pycache__':
        print(f"Processing cache: {root}")
        # 将所有 .pyc 文件移动到上一级目录
        for file in os.listdir(root):
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                # 重命名，去掉中间的 .cpython-310 部分
                new_name = file.split('.')[0] + '.pyc'
                dest_path = os.path.join(os.path.dirname(root), new_name)
                print(f"  Moving and renaming {pyc_path} to {dest_path}")
                shutil.move(pyc_path, dest_path)
        # 删除空的 __pycache__ 文件夹
        print(f"  Removing empty cache folder: {root}")
        os.rmdir(root)
        continue # 处理完 __pycache__，直接进入下一次循环

    # 2. 删除所有 .py 源代码文件
    for name in files:
        if name.endswith('.py'):
            file_path = os.path.join(root, name)
            # 关键：只删除与.pyc同名的.py文件，保留我们自己这个脚本
            if os.path.exists(file_path.replace('.py', '.pyc')) or name != os.path.basename(__file__):
                print(f"Deleting source file: {file_path}")
                os.remove(file_path)

print("--- Cleanup complete! ---")