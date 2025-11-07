# core/data_loader.py (修复版 - 智能路径搜索)

import json
import os
import rasterio
import numpy as np
from PIL import Image

class DataLoader:
    """数据加载工具集"""

    @staticmethod
    def load_dem(dem_path):
        """加载数字高程模型 (DEM) 文件。"""
        try:
            with rasterio.open(dem_path) as src:
                dem_data = src.read(1)
                dem_transform = src.transform
                print(f"✅ DEM loaded from '{dem_path}'")
                return dem_data, dem_transform
        except Exception as e:
            print(f"❌ FATAL ERROR loading DEM: {e}")
            return None, None

    @staticmethod
    def load_camera_params(camera_params_path):
        """加载相机参数 JSON 文件。"""
        try:
            with open(camera_params_path, 'r') as f:
                params = json.load(f)
                print(f"✅ Camera parameters loaded from '{camera_params_path}'")
                return params
        except Exception as e:
            print(f"❌ FATAL ERROR processing camera params: {e}")
            return None

    @staticmethod
    def get_available_yolo_labels(yolo_dataset_dir):
        """扫描并返回所有可用的YOLO标签文件名（兼容多种目录结构）"""
        if not yolo_dataset_dir or not os.path.isdir(yolo_dataset_dir):
            print(f"⚠️ Warning: YOLO dataset directory not found at '{yolo_dataset_dir}'")
            return []

        labels_dir = os.path.join(yolo_dataset_dir, 'labels')
        images_dir = os.path.join(yolo_dataset_dir, 'images')
        
        if not os.path.isdir(labels_dir): 
            labels_dir = yolo_dataset_dir
        if not os.path.isdir(images_dir): 
            images_dir = yolo_dataset_dir

        available_files = []
        if not os.path.isdir(labels_dir):
            print(f"⚠️ Warning: Could not find a valid labels directory in '{yolo_dataset_dir}'")
            return []
            
        for label_file in os.listdir(labels_dir):
            if label_file.endswith('.txt'):
                base_name = os.path.splitext(label_file)[0]
                for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']:
                    image_file = base_name + ext
                    if os.path.exists(os.path.join(images_dir, image_file)):
                        available_files.append(image_file)
                        break
        
        print(f"✅ Found {len(available_files)} available YOLO image/label pairs.")
        return sorted(available_files)

    @staticmethod
    def load_yolo_detections(yolo_dataset_dir, image_filename):
        """
        ✅ 修复版：智能搜索YOLO文件路径（支持多种目录结构）
        
        搜索顺序：
        1. yolo_dataset_dir/labels/xxx.txt
        2. yolo_dataset_dir/train/labels/xxx.txt
        3. yolo_dataset_dir/valid/labels/xxx.txt
        4. yolo_dataset_dir/xxx.txt（直接在根目录）
        """
        if not yolo_dataset_dir or not image_filename:
            return None
        
        # 提取基础文件名（去掉扩展名）
        base_name = os.path.splitext(image_filename)[0]
        label_filename = f'{base_name}.txt'
        
        # ✅ 定义多个可能的路径
        possible_paths = [
            # 标准YOLO结构
            os.path.join(yolo_dataset_dir, 'labels', label_filename),
            os.path.join(yolo_dataset_dir, 'images', label_filename),
            
            # train/valid 分割结构
            os.path.join(yolo_dataset_dir, 'train', 'labels', label_filename),
            os.path.join(yolo_dataset_dir, 'valid', 'labels', label_filename),
            os.path.join(yolo_dataset_dir, 'test', 'labels', label_filename),
            
            # 根目录
            os.path.join(yolo_dataset_dir, label_filename),
        ]
        
        # 查找第一个存在的文件
        label_path = None
        for path in possible_paths:
            if os.path.exists(path):
                label_path = path
                break
        
        if label_path is None:
            print(f"   ⚠️ Warning: YOLO label file not found for '{image_filename}'")
            print(f"      Searched in: {yolo_dataset_dir}")
            return None
        
        # ✅ 同样智能搜索对应的图像文件
        image_extensions = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']
        image_path = None
        
        possible_image_dirs = [
            os.path.join(yolo_dataset_dir, 'images'),
            os.path.join(yolo_dataset_dir, 'train', 'images'),
            os.path.join(yolo_dataset_dir, 'valid', 'images'),
            os.path.join(yolo_dataset_dir, 'test', 'images'),
            yolo_dataset_dir,
        ]
        
        for img_dir in possible_image_dirs:
            for ext in image_extensions:
                test_path = os.path.join(img_dir, base_name + ext)
                if os.path.exists(test_path):
                    image_path = test_path
                    break
            if image_path:
                break
        
        if image_path is None:
            print(f"   ⚠️ Warning: Image file not found for '{image_filename}'")
            return None
        
        try:
            # 读取图像尺寸
            with Image.open(image_path) as img:
                img_width, img_height = img.size

            # 读取标签文件
            detections_px = []
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        x_center_norm, y_center_norm = float(parts[1]), float(parts[2])
                        px = int(x_center_norm * img_width)
                        py = int(y_center_norm * img_height)
                        detections_px.append((px, py))
            
            print(f"   ✅ Loaded {len(detections_px)} detections from '{os.path.basename(label_path)}'")
            return np.array(detections_px)
            
        except Exception as e:
            print(f"   ❌ ERROR processing YOLO file '{image_filename}': {e}")
            return None
