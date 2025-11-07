# core/dem_generator.py (Phase 1.8 坐标对齐版)

import numpy as np
import affine

def create_slope_dem(slope_deg=15.0, base_elevation=100.0):
    """
    创建一个与真实地形坐标对齐的虚拟斜坡DEM。
    
    核心改进：
    - 使用与真实地形相同的坐标范围
    - 确保相机和YOLO数据可以直接复用
    
    坐标系统：
    - X范围：[300000, 305000] (5000米)
    - Y范围：[3995000, 4000000] (5000米)
    - 分辨率：1米
    
    Args:
        slope_deg (float): 坡度角度（度）
        base_elevation (float): 南边缘（Y最小处）的基准高程
    
    Returns:
        tuple: (dem_data, dem_transform)
    """
    # ✅ 修改：使用与真实地形相同的范围和分辨率
    width, height = 8000, 8000  # 5km × 5km
    resolution = 1.0
    origin_x = 300000.0  # 西边界
    origin_y = 4000000.0  # 北边界（最大Y值）
    
    # 计算高程变化
    total_distance = height * resolution  # 5000米
    tan_slope = np.tan(np.deg2rad(slope_deg))
    elevation_change = total_distance * tan_slope
    
    # 创建高程数组
    dem_data = np.zeros((height, width), dtype=np.float32)
    
    for row in range(height):
        # row=0 (北边，Y=4000000) -> 高程最高
        # row=4999 (南边，Y=3995001) -> 高程最低
        elevation = base_elevation + elevation_change * (1 - row / (height - 1))
        dem_data[row, :] = elevation
    
    # 创建仿射变换
    transform = affine.Affine(
        resolution, 0.0, origin_x,
        0.0, -resolution, origin_y
    )
    
    z_min, z_max = np.min(dem_data), np.max(dem_data)
    
    print(f"✅ Generated virtual DEM (coordinate-aligned):")
    print(f"   - Size: {width}×{height} pixels, resolution: {resolution}m")
    print(f"   - Slope: {slope_deg}°, elevation range: [{z_min:.1f}, {z_max:.1f}]m")
    print(f"   - World bounds: X=[{origin_x:.0f}, {origin_x + width * resolution:.0f}], "
          f"Y=[{origin_y - height * resolution:.0f}, {origin_y:.0f}]")
    
    return dem_data, transform
