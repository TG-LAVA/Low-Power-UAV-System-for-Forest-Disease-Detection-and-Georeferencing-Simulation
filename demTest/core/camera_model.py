# core/camera_model.py (性能优化版 - 批量投影)

import numpy as np
import rasterio

class CameraModel:
    """
    封装相机模型，处理从像素坐标到相机坐标系下的3D视线向量的转换。
    ✅ Phase 3 优化：支持批量投影
    """
    def __init__(self, camera_params):
        """初始化相机模型"""
        intrinsics = camera_params['camera_intrinsics']
        
        self.f_px = intrinsics['focal_length_px']
        sensor_size = intrinsics['sensor_size_px']
        self.w_px = sensor_size[0]
        self.h_px = sensor_size[1]
        
        if 'principal_point_px' in intrinsics:
            self.cx = intrinsics['principal_point_px'][0]
            self.cy = intrinsics['principal_point_px'][1]
        else:
            self.cx = self.w_px / 2.0
            self.cy = self.h_px / 2.0
        
        extrinsics = camera_params['camera_extrinsics']
        rotation = extrinsics['rotation_degrees']
        self.roll = rotation['roll']
        self.pitch = rotation['pitch']
        self.yaw = rotation['yaw']
        
        self.R_cam_to_world = self._create_rotation_matrix(self.roll, self.pitch, self.yaw)
        self.camera_pos_world = np.array(extrinsics['position_meters'], dtype=np.float64)

    def _create_rotation_matrix(self, roll_deg, pitch_deg, yaw_deg):
        """根据欧拉角创建旋转矩阵"""
        gamma = np.deg2rad(roll_deg)
        beta = np.deg2rad(pitch_deg)
        alpha = np.deg2rad(yaw_deg)

        Rx = np.array([[1, 0, 0], 
                       [0, np.cos(gamma), -np.sin(gamma)], 
                       [0, np.sin(gamma), np.cos(gamma)]])
        
        Ry = np.array([[np.cos(beta), 0, np.sin(beta)], 
                       [0, 1, 0], 
                       [-np.sin(beta), 0, np.cos(beta)]])
        
        Rz = np.array([[np.cos(alpha), -np.sin(alpha), 0], 
                       [np.sin(alpha), np.cos(alpha), 0], 
                       [0, 0, 1]])
        
        R_user = Rz @ Ry @ Rx
        
        R_base = np.array([
            [1, 0, 0],
            [0, -1, 0],
            [0, 0, -1]
        ])
        
        return R_user @ R_base

    def pixel_to_ray(self, pixel_coord):
        """将像素坐标转换为世界坐标系下的射线（起点和方向）"""
        u, v = pixel_coord
        
        x_prime = u - self.cx
        y_prime = self.cy - v
        
        vec_camera = np.array([x_prime, y_prime, self.f_px])
        ray_direction_world = self.R_cam_to_world @ vec_camera
        
        norm = np.linalg.norm(ray_direction_world)
        if norm < 1e-9:
            return self.camera_pos_world, np.array([0, 0, -1.0])
        
        ray_direction_normalized = ray_direction_world / norm
        
        return self.camera_pos_world, ray_direction_normalized.astype(np.float64)

    # ✅ 新增：批量世界坐标转相机坐标
    def world_to_camera_batch(self, world_points):
        """
        批量将世界坐标系中的点转换到相机坐标系（向量化）
        
        参数:
            world_points: np.array, shape (N, 3), 世界坐标系中的点
        
        返回:
            camera_points: np.array, shape (N, 3), 相机坐标系中的点
        """
        # 平移
        translated = world_points - self.camera_pos_world
        
        # 旋转（矩阵乘法的向量化形式）
        # R_world_to_cam 是 R_cam_to_world 的转置
        R_world_to_cam = self.R_cam_to_world.T
        camera_points = (R_world_to_cam @ translated.T).T
        
        return camera_points

    # ✅ 新增：批量投影
    def project_points_batch(self, world_points):
        """
        批量投影世界坐标到图像坐标（向量化）
        
        参数:
            world_points: np.array, shape (N, 3), 世界坐标系中的3D点
        
        返回:
            image_points: np.array, shape (N, 2), 图像坐标（像素）
            valid_mask: np.array, shape (N,), bool值，标记哪些点投影成功
        """
        N = world_points.shape[0]
        image_points = np.zeros((N, 2))
        valid_mask = np.zeros(N, dtype=bool)
        
        # 批量转换到相机坐标系
        pts_camera = self.world_to_camera_batch(world_points)
        
        # 检查点是否在相机前方（Z > 0）
        front_mask = pts_camera[:, 2] > 0
        
        if np.any(front_mask):
            valid_pts = pts_camera[front_mask]
            
            # 透视投影 (X/Z, Y/Z)
            x_normalized = valid_pts[:, 0] / valid_pts[:, 2]
            y_normalized = valid_pts[:, 1] / valid_pts[:, 2]
            
            # 应用内参矩阵
            pixel_x = self.f_px * x_normalized + self.cx
            pixel_y = self.cy - self.f_px * y_normalized  # 注意Y轴翻转
            
            # 检查是否在图像范围内
            in_bounds = (
                (pixel_x >= 0) & (pixel_x < self.w_px) &
                (pixel_y >= 0) & (pixel_y < self.h_px)
            )
            
            # 填充结果
            valid_indices = np.where(front_mask)[0]
            final_valid = valid_indices[in_bounds]
            
            image_points[final_valid, 0] = pixel_x[in_bounds]
            image_points[final_valid, 1] = pixel_y[in_bounds]
            valid_mask[final_valid] = True
        
        return image_points, valid_mask

    def world_to_pixel(self, world_point):
        """将世界坐标点投影到像素坐标系（单点版本，保持兼容性）"""
        P_world = np.array(world_point) - self.camera_pos_world
        R_world_to_cam = self.R_cam_to_world.T
        P_cam = R_world_to_cam @ P_world
        
        if P_cam[2] <= 0:
            return None
        
        x_normalized = P_cam[0] / P_cam[2]
        y_normalized = P_cam[1] / P_cam[2]
        
        u = self.f_px * x_normalized + self.cx
        v = self.cy - self.f_px * y_normalized
        
        if 0 <= u < self.w_px and 0 <= v < self.h_px:
            return (u, v)
        else:
            return None

    # core/camera_model.py

    def compute_ground_coverage(self, ground_elevation=0):
        """
        ✅ 精确计算相机在给定地面高程下的覆盖范围
        使用射线-平面相交法，完全考虑相机的所有姿态参数
        
        Args:
            ground_elevation: 地面高程（米）
        
        Returns:
            footprint: 覆盖范围四边形顶点列表 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
            coverage_radius: 覆盖范围的近似半径（米）
        """
        # 检查相机高度
        height_agl = self.camera_pos_world[2] - ground_elevation
        
        if height_agl <= 0:
            print(f"   ⚠️ Warning: Camera below ground! Height AGL: {height_agl:.2f} m")
            return [], 0
        
        # ✅ 关键改进：计算图像四个角点的射线与地面平面的交点
        
        # 定义图像四个角点（像素坐标）
        # 左上、右上、右下、左下
        image_corners = [
            (0, 0),                    # 左上
            (self.w_px - 1, 0),        # 右上
            (self.w_px - 1, self.h_px - 1),  # 右下
            (0, self.h_px - 1)         # 左下
        ]
        
        footprint = []
        
        for pixel_coord in image_corners:
            # 获取该像素对应的世界坐标系射线
            ray_origin, ray_direction = self.pixel_to_ray(pixel_coord)
            
            # 计算射线与地面平面 (z = ground_elevation) 的交点
            # 射线方程: P = ray_origin + t * ray_direction
            # 平面方程: z = ground_elevation
            # 解方程: ray_origin[2] + t * ray_direction[2] = ground_elevation
            
            if abs(ray_direction[2]) < 1e-9:
                # 射线几乎平行于地面，无法相交
                print(f"   ⚠️ Warning: Ray parallel to ground for corner {pixel_coord}")
                continue
            
            # 求参数t
            t = (ground_elevation - ray_origin[2]) / ray_direction[2]
            
            if t < 0:
                # 交点在相机后方（不应该发生，除非地面高于相机）
                print(f"   ⚠️ Warning: Intersection behind camera for corner {pixel_coord}")
                continue
            
            # 计算交点的世界坐标
            intersection_point = ray_origin + t * ray_direction
            
            footprint.append((intersection_point[0], intersection_point[1]))
        
        # 如果没有成功计算出四个角点，返回空结果
        if len(footprint) != 4:
            print(f"   ❌ Error: Could not compute all 4 corners. Only got {len(footprint)} points.")
            return [], 0
        
        # 计算覆盖范围的近似半径（中心到角点的平均距离）
        center_x = np.mean([p[0] for p in footprint])
        center_y = np.mean([p[1] for p in footprint])
        
        distances = [np.sqrt((p[0] - center_x)**2 + (p[1] - center_y)**2) for p in footprint]
        coverage_radius = np.mean(distances)
        
        return footprint, coverage_radius

