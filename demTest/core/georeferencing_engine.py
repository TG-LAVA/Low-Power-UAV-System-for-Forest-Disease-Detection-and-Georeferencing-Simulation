# core/georeferencing_engine.py (性能优化版)

import numpy as np
import rasterio
from scipy.interpolate import RegularGridInterpolator

class GeoreferencingEngine:
    """
    核心计算引擎，负责实现视线与DEM地形的求交算法。
    ✅ Phase 3 优化：预加载DEM、快速插值、批量查询
    """
    def __init__(self, dem_data, dem_transform):
        """
        使用从DataLoader加载的DEM数据进行初始化。
        """
        self.dem = dem_data
        self.transform = dem_transform
        self.inv_transform = ~self.transform
        self.dem_height, self.dem_width = self.dem.shape
        self.dem_transform = dem_transform 
        
        # 计算DEM的世界坐标范围（用于边界检查）
        self.dem_bounds = {
            'min_x': self.transform.c,
            'max_x': self.transform.c + self.transform.a * self.dem_width,
            'min_y': self.transform.f + self.transform.e * self.dem_height,
            'max_y': self.transform.f
        }
        
        # ✅ 性能优化：创建快速插值器
        self.interpolator = self._create_interpolator()
        
        print("✅ GeoreferencingEngine initialized (Optimized).")
        print(f"   - DEM Grid Size: {self.dem_width}x{self.dem_height}")
        print(f"   - DEM World Bounds: X=[{self.dem_bounds['min_x']:.0f}, {self.dem_bounds['max_x']:.0f}], "
              f"Y=[{self.dem_bounds['min_y']:.0f}, {self.dem_bounds['max_y']:.0f}]")
        print(f"   - DEM Memory: {self.dem.nbytes / 1024 / 1024:.2f} MB")
        print(f"   - Fast Interpolator: Ready ⚡")

    def _create_interpolator(self):
        """创建快速插值器（用于批量查询）"""
        height, width = self.dem.shape
        
        # 创建世界坐标网格
        x_coords = np.linspace(
            self.dem_bounds['min_x'], 
            self.dem_bounds['max_x'], 
            width
        )
        y_coords = np.linspace(
            self.dem_bounds['max_y'],  # 注意：Y轴从上到下
            self.dem_bounds['min_y'], 
            height
        )
        
        # 创建插值器（注意：需要(y, x)顺序）
        interpolator = RegularGridInterpolator(
            (y_coords, x_coords),
            self.dem,
            method='linear',
            bounds_error=False,
            fill_value=np.nan
        )
        
        return interpolator

    def get_elevation_at_coord(self, x, y, silent=False):
        """
        根据世界坐标(x, y)查询DEM高程（兼容旧代码）
        
        参数:
        - x, y: 世界坐标（如UTM坐标）
        - silent: 是否抑制日志输出
        
        返回:
        - elevation: 高程值，如果超出范围则返回None
        """
        try:
            row, col = rasterio.transform.rowcol(self.transform, x, y)
            
            if 0 <= row < self.dem_height and 0 <= col < self.dem_width:
                elevation = self.dem[row, col]
                if not silent:
                    print(f"   ✅ 世界({x:.0f},{y:.0f}) -> 栅格({col},{row}) -> 高程{elevation:.2f}m")
                return elevation
            else:
                if not silent:
                    print(f"   ❌ 世界({x:.0f},{y:.0f}) -> 栅格({col},{row}) 超出DEM范围")
                return None
        except Exception as e:
            if not silent:
                print(f"   ❌ 坐标转换失败: {e}")
            return None

    def get_elevation_at_point(self, world_xy):
        """
        获取给定世界坐标(x, y)点的DEM高程。
        ✅ 优化版本：使用快速插值器
        
        Args:
            world_xy (np.ndarray or tuple): 包含世界坐标X和Y的数组或元组
        
        Returns:
            float: 该点的高程值，如果点在DEM范围外则返回None
        """
        if isinstance(world_xy, (list, tuple)):
            x, y = world_xy[0], world_xy[1]
        else:
            x, y = world_xy[0], world_xy[1]
        
        # 边界检查
        if not (self.dem_bounds['min_x'] <= x <= self.dem_bounds['max_x'] and
                self.dem_bounds['min_y'] <= y <= self.dem_bounds['max_y']):
            return None
        
        # ✅ 使用快速插值器
        if self.interpolator is not None:
            elevation = self.interpolator([y, x])[0]  # 注意：(y, x)顺序
            return float(elevation) if not np.isnan(elevation) else None
        
        # 回退到传统方法（如果插值器失败）
        col, row = ~self.dem_transform * (x, y)
        num_rows, num_cols = self.dem.shape
        
        if not (0 <= row < num_rows - 1 and 0 <= col < num_cols - 1):
            return None
        
        # 双线性插值（手动实现）
        r_int, c_int = int(row), int(col)
        r_frac, c_frac = row - r_int, col - c_int
        
        z11 = self.dem[r_int, c_int]
        z12 = self.dem[r_int, c_int + 1]
        z21 = self.dem[r_int + 1, c_int]
        z22 = self.dem[r_int + 1, c_int + 1]
        
        z_r1 = (1 - c_frac) * z11 + c_frac * z12
        z_r2 = (1 - c_frac) * z21 + c_frac * z22
        interpolated_z = (1 - r_frac) * z_r1 + r_frac * z_r2
        
        return interpolated_z

    def get_elevation_batch(self, points_xy):
        """
        ✅ 新增：批量获取多个点的高程值（向量化操作）
        
        参数:
            points_xy: np.array, shape (N, 2), 世界坐标 [(x1, y1), (x2, y2), ...]
        
        返回:
            elevations: np.array, shape (N,), 高程值（超出范围的点为NaN）
        """
        if self.interpolator is None:
            raise RuntimeError("Interpolator not initialized")
        
        N = points_xy.shape[0]
        
        # 转换为(y, x)顺序
        points_yx = points_xy[:, [1, 0]]
        
        # 批量插值（这是性能提升的关键！）
        elevations = self.interpolator(points_yx)
        
        return elevations

    def intersect_ray_with_dem(self, ray_origin, ray_direction, 
                               step_size=None, max_steps=None):
        """
        【完全重构版】计算射线与DEM的交点
        
        核心改进：
        1. 自动计算合理的步长和最大步数
        2. 快速粗定位 + 精确细定位两阶段算法
        3. 严格的边界检查和向下射线验证
        """
        
        # === 第0步：验证射线有效性 ===
        if ray_direction[2] >= 0:
            print(f"   ⚠️ 警告：射线向上或水平 (Z方向={ray_direction[2]:.3f})，无法击中地面")
            return None
        
        # 归一化射线方向
        ray_direction = ray_direction / np.linalg.norm(ray_direction)
        
        # === 第1步：智能计算参数 ===
        dem_max_elevation = np.max(self.dem)
        dem_min_elevation = np.min(self.dem)
        
        vertical_distance = ray_origin[2] - dem_min_elevation
        
        if vertical_distance <= 0:
            print(f"   ❌ 错误：相机位于地面以下！相机Z={ray_origin[2]:.1f}m, DEM最低点={dem_min_elevation:.1f}m")
            return None
        
        cos_angle = abs(ray_direction[2])
        estimated_ray_length = vertical_distance / cos_angle
        
        dem_resolution = max(abs(self.transform.a), abs(self.transform.e))
        
        if step_size is None:
            step_size_coarse = dem_resolution * 5.0
        else:
            step_size_coarse = step_size
        
        if max_steps is None:
            max_steps = int(estimated_ray_length / step_size_coarse) + 100
            max_steps = max(1000, max_steps)
        
        # 减少日志输出（只在需要时打印）
        # print(f"   🔍 射线求交 (自适应参数):")
        # print(f"      起点: ({ray_origin[0]:.1f}, {ray_origin[1]:.1f}, {ray_origin[2]:.1f})")
        # print(f"      方向: ({ray_direction[0]:.3f}, {ray_direction[1]:.3f}, {ray_direction[2]:.3f})")
        
        # === 第2步：粗定位阶段（快速找到大致区域）===
        current_point = np.copy(ray_origin).astype(np.float64)
        prev_point = None
        prev_elevation = None
        
        for i in range(max_steps):
            current_point = current_point + ray_direction * step_size_coarse
            
            # 边界检查
            if not (self.dem_bounds['min_x'] <= current_point[0] <= self.dem_bounds['max_x'] and
                    self.dem_bounds['min_y'] <= current_point[1] <= self.dem_bounds['max_y']):
                # print(f"   ❌ 第{i}步射线飞出DEM边界")
                return None
            
            # ✅ 使用优化的高程查询
            ground_elevation = self.get_elevation_at_point(current_point[:2])
            
            if ground_elevation is None:
                return None
            
            # 检查是否穿过地面
            if current_point[2] <= ground_elevation:
                # === 第3步：精确定位阶段（二分查找） ===
                if prev_point is not None:
                    intersection = self._bisect_intersection(
                        prev_point, current_point,
                        prev_elevation, ground_elevation
                    )
                else:
                    intersection = np.array([
                        current_point[0],
                        current_point[1],
                        ground_elevation
                    ])
                
                return intersection
            
            prev_point = np.copy(current_point)
            prev_elevation = ground_elevation
        
        return None

    def _bisect_intersection(self, point1, point2, elev1, elev2, max_iter=10):
        """
        二分法精确定位交点
        """
        for iteration in range(max_iter):
            mid_point = (point1 + point2) / 2
            mid_elev = self.get_elevation_at_point(mid_point[:2])
            
            if mid_elev is None:
                break
            
            # 精度达标
            if abs(mid_point[2] - mid_elev) < 0.1:
                return np.array([mid_point[0], mid_point[1], mid_elev])
            
            # 判断交点在哪一半
            if mid_point[2] > mid_elev:
                point1 = mid_point
                elev1 = mid_elev
            else:
                point2 = mid_point
                elev2 = mid_elev
        
        # 返回最终估计
        final_point = (point1 + point2) / 2
        final_elev = self.get_elevation_at_point(final_point[:2])
        return np.array([final_point[0], final_point[1], final_elev if final_elev else final_point[2]])
    
    def georeference_point(self, pixel_coord, camera_model):
        """
        对单个像素点进行地理配准
        """
        ray_origin, ray_direction = camera_model.pixel_to_ray(pixel_coord)
        
        intersection = self.intersect_ray_with_dem(
            ray_origin=ray_origin,
            ray_direction=ray_direction
        )
        
        if intersection is not None:
            return {
                'success': True,
                'world_x': intersection[0],
                'world_y': intersection[1],
                'world_z': intersection[2]
            }
        else:
            return {
                'success': False,
                'world_x': None,
                'world_y': None,
                'world_z': None
            }
