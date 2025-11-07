# app.py (最终集成版)

import sys
import json
from PyQt6.QtWidgets import QApplication
from gui.app_window import AppWindow
import matplotlib.pyplot as plt

# ✅ 导入 DataLoader 以便扫描YOLO文件
from core.data_loader import DataLoader 

def set_matplotlib_font():
    """
    为 Matplotlib 设置支持中文的字体。
    它会尝试一系列常见的中文字体，直到找到一个可用的。
    """
    font_candidates = [
        'SimHei',           # 黑体
        'Microsoft YaHei',  # 微软雅黑
        'FangSong',         # 仿宋
        'KaiTi',            # 楷体
        'Arial Unicode MS'  # 一个常用的Unicode字体
    ]
    
    for font in font_candidates:
        try:
            plt.rcParams['font.sans-serif'] = [font]
            plt.rcParams['axes.unicode_minus'] = False
            fig, ax = plt.subplots()
            ax.set_title("测试")
            plt.close(fig)
            print(f"✅ Matplotlib font set to '{font}' successfully.")
            return
        except Exception:
            continue
            
    print("⚠️ Warning: No suitable Chinese font found. Display might show garbled characters.")


def main():
    """程序主入口"""
    # 1. 设置 Matplotlib 全局字体
    set_matplotlib_font()

    # 2. 加载配置文件
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ FATAL: config.json not found!")
        return
    except json.JSONDecodeError:
        print("❌ FATAL: config.json is not a valid JSON file!")
        return

    # 3. 创建Qt应用程序实例
    app = QApplication(sys.argv)
    
    # 4. 创建主窗口
    main_window = AppWindow(config)
    
    # ------------------- 新增逻辑开始 -------------------
    # ✅ 5. 扫描并填充YOLO文件列表 (修复Bug 2)
    #    在主窗口创建后、显示前，执行此操作。
    print("UI: Populating YOLO file list...")
    try:
        yolo_dir = config.get('data_paths', {}).get('yolo_dataset_dir', '')
        if yolo_dir:
            # 调用 DataLoader 的静态方法扫描目录
            available_files = DataLoader.get_available_yolo_labels(yolo_dir)
            # 调用 ControlPanel 的方法来设置下拉框内容
            main_window.control_panel.set_available_yolo_files(available_files)
        else:
            print("⚠️ Warning: 'yolo_dataset_dir' not specified in config.json.")
            main_window.control_panel.set_available_yolo_files([]) # 传递空列表
    except Exception as e:
        print(f"❌ Error while populating YOLO files: {e}")
        main_window.control_panel.set_available_yolo_files([]) # 出错时也传递空列表
    # ------------------- 新增逻辑结束 -------------------

    # 6. 显示主窗口并启动事件循环
    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
