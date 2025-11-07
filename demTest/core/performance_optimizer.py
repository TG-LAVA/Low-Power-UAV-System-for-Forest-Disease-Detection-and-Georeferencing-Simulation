# core/performance_optimizer.py

import numpy as np
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

class PerformanceOptimizer:
    """性能优化器：负责预加载、缓存和并行计算"""
    
    def __init__(self, max_workers=None):
        # 使用CPU核心数作为默认worker数
        self.max_workers = max_workers or max(1, mp.cpu_count() - 1)
        print(f"PerformanceOptimizer: Initialized with {self.max_workers} workers.")
    
    @staticmethod
    def batch_project_points(camera_model, world_points_3d):
        """
        批量投影3D世界点到图像平面（向量化操作）
        
        参数:
            camera_model: CameraModel实例
            world_points_3d: np.array, shape (N, 3), 世界坐标系中的3D点
        
        返回:
            image_points: np.array, shape (N, 2), 图像坐标（像素）
            valid_mask: np.array, shape (N,), bool值，标记哪些点投影成功
        """
        N = world_points_3d.shape[0]
        image_points = np.zeros((N, 2))
        valid_mask = np.zeros(N, dtype=bool)
        
        # 批量转换到相机坐标系
        pts_camera = camera_model.world_to_camera_batch(world_points_3d)
        
        # 检查点是否在相机前方（Z > 0）
        front_mask = pts_camera[:, 2] > 0
        
        if np.any(front_mask):
            # 只对有效点进行投影
            valid_pts = pts_camera[front_mask]
            
            # 透视投影 (X/Z, Y/Z)
            normalized = valid_pts[:, :2] / valid_pts[:, 2:3]
            
            # 应用畸变（如果有的话，这里简化处理，假设无畸变或已在相机模型中处理）
            # distorted = camera_model.apply_distortion_batch(normalized)
            distorted = normalized  # 暂时跳过畸变
            
            # 应用内参矩阵
            fx, fy = camera_model.fx, camera_model.fy
            cx, cy = camera_model.cx, camera_model.cy
            
            pixel_x = distorted[:, 0] * fx + cx
            pixel_y = distorted[:, 1] * fy + cy
            
            # 检查是否在图像范围内
            in_bounds = (
                (pixel_x >= 0) & (pixel_x < camera_model.width) &
                (pixel_y >= 0) & (pixel_y < camera_model.height)
            )
            
            # 填充结果
            valid_indices = np.where(front_mask)[0]
            final_valid = valid_indices[in_bounds]
            
            image_points[final_valid, 0] = pixel_x[in_bounds]
            image_points[final_valid, 1] = pixel_y[in_bounds]
            valid_mask[final_valid] = True
        
        return image_points, valid_mask
    
    @staticmethod
    def parallel_camera_simulation(camera_configs, yolo_data, geo_engine):
        """
        使用进程池并行处理多个相机的模拟（用于航线模拟）
        
        参数:
            camera_configs: list of dict, 每个dict包含相机参数和航点信息
            yolo_data: YOLO标注数据
            geo_engine: GeoEngine实例
        
        返回:
            results: list of dict, 每个相机的模拟结果
        """
        # 注意：由于pickle限制，这里需要特殊处理
        # 实际实现中可能需要将GeoEngine改为可序列化的形式
        # 或者使用共享内存
        
        # 这是一个框架示例，实际实现可能需要更复杂的序列化处理
        print(f"  [Parallel] Processing {len(camera_configs)} cameras...")
        
        # 简化版：仍使用单进程，但批处理
        # 完整的多进程实现需要解决序列化问题
        results = []
        for config in camera_configs:
            # 调用单个相机的模拟逻辑
            result = PerformanceOptimizer._simulate_single_camera(
                config, yolo_data, geo_engine
            )
            results.append(result)
        
        return results
    
    @staticmethod
    def _simulate_single_camera(camera_config, yolo_data, geo_engine):
        """单个相机的模拟逻辑（辅助方法）"""
        # 这个方法将在后面整合到BackendService中
        pass
