# create_virtual_slope_dem.py
# 用于生成虚拟斜坡DEM的独立脚本

import numpy as np
import rasterio
from rasterio.transform import from_origin
import os

def generate_dem(filename, mode, config):
    """
    生成一个带有地理参考的DEM TIF文件。
    (此函数直接来自您提供的可靠代码)
    """
    print(f"--- Generating DEM: '{filename}' (Mode: {mode}) ---")

    width = config['size_pixels'][0]
    height = config['size_pixels'][1]
    
    # 创建坐标网格
    x = np.linspace(0, width - 1, width)
    y = np.linspace(0, height - 1, height)
    xx, yy = np.meshgrid(x, y)

    # 根据模式生成高程数据
    if mode == 'simple':
        base_elevation = config['base_elevation']
        slope_deg = config['slope_deg']
        slope_direction_deg = config['slope_direction_deg']
        
        # 将坡度方向转换为单位向量
        slope_rad = np.deg2rad(slope_direction_deg)
        direction_vector = np.array([np.cos(slope_rad), np.sin(slope_rad)])
        
        # 计算每个点的坡度贡献
        center_x, center_y = width / 2, height / 2
        slope_contribution = ( (xx - center_x) * direction_vector[0] + 
                               (yy - center_y) * direction_vector[1] )
        
        # 坡度值转为每个像素的高度增量
        tan_slope = np.tan(np.deg2rad(slope_deg))
        elevation_gain = slope_contribution * tan_slope * config['resolution_m']
        
        dem_data = base_elevation + elevation_gain
        print(f"  - Type: Simple Slope")
        print(f"  - Base Elevation: {base_elevation}m, Slope: {slope_deg}°, Direction: {slope_direction_deg}°")

    else:
        raise ValueError("Mode must be 'simple'")

    # --- 写入带有地理参考的TIF文件 ---
    transform = from_origin(
        west=config['origin_xy'][0], 
        north=config['origin_xy'][1], 
        xsize=config['resolution_m'], 
        ysize=config['resolution_m']
    )
    
    crs = 'EPSG:32610' # UTM Zone 10N

    # 确保输出目录存在
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with rasterio.open(
        filename,
        'w',
        driver='GTiff',
        height=dem_data.shape[0],
        width=dem_data.shape[1],
        count=1,
        dtype=dem_data.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(dem_data.astype(rasterio.float32), 1)

    print(f"✅ DEM successfully saved to '{filename}'")
    print(f"   - Dimensions: {width}x{height} pixels")
    print(f"   - Resolution: {config['resolution_m']} m/pixel")
    print(f"   - Geo Origin (Top-Left): X={config['origin_xy'][0]}, Y={config['origin_xy'][1]}")
    print(f"   - CRS: {crs}")


if __name__ == '__main__':
    # 生成一个简单的虚拟斜坡DEM
    simple_config = {
        'size_pixels': (500, 500),
        'resolution_m': 1.0,
        'origin_xy': (300000, 4000000),
        'base_elevation': 100.0,
        'slope_deg': 15.0,
        'slope_direction_deg': 180.0  # 西向 (高程从东向西增加)
    }
    generate_dem(
        filename='./data/virtual_slope_dem.tif', 
        mode='simple', 
        config=simple_config
    )