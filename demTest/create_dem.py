import numpy as np
import rasterio
from rasterio.transform import from_origin

def generate_dem(filename, mode, config):
    """
    生成一个带有地理参考的DEM TIF文件。

    参数:
    - filename (str): 输出的TIF文件名 (例如 'complex_virtual_dem.tif')
    - mode (str): 'simple' 或 'complex'
    - config (dict): 地形生成参数
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
        # (xx, yy) 点积方向向量，得到在该方向上的投影长度
        # 我们需要以图像中心为原点计算坡度
        center_x, center_y = width / 2, height / 2
        slope_contribution = ( (xx - center_x) * direction_vector[0] + 
                               (yy - center_y) * direction_vector[1] )
        
        # 坡度值转为每个像素的高度增量
        tan_slope = np.tan(np.deg2rad(slope_deg))
        elevation_gain = slope_contribution * tan_slope * config['resolution_m']
        
        dem_data = base_elevation + elevation_gain
        print(f"  - Type: Simple Slope")
        print(f"  - Base Elevation: {base_elevation}m, Slope: {slope_deg}°, Direction: {slope_direction_deg}°")

    elif mode == 'complex':
        dem_data = np.full((height, width), config.get('base_elevation', 800.0))
        
        # 添加多个高斯山峰/山谷
        for peak in config['peaks']:
            amp = peak['amplitude']  # 振幅 (山峰高度或山谷深度)
            cx, cy = peak['center_xy_ratio'] # 中心点比例位置
            sx, sy = peak['sigma_xy_ratio']  # 影响范围比例
            
            # 转换为像素坐标
            center_x, center_y = cx * width, cy * height
            sigma_x, sigma_y = sx * width, sy * height
            
            # 创建高斯函数
            exponent = -(((xx - center_x)**2 / (2 * sigma_x**2)) + ((yy - center_y)**2 / (2 * sigma_y**2)))
            dem_data += amp * np.exp(exponent)
        
        print(f"  - Type: Complex Terrain")
        print(f"  - Added {len(config['peaks'])} features (peaks/valleys).")

    else:
        raise ValueError("Mode must be 'simple' or 'complex'")

    # --- 写入带有地理参考的TIF文件 ---
    # 定义地理变换信息
    transform = from_origin(
        west=config['origin_xy'][0], 
        north=config['origin_xy'][1], 
        xsize=config['resolution_m'], 
        ysize=config['resolution_m']
    )
    
    # 定义坐标参考系统 (CRS) - 这里使用一个常见的UTM带
    crs = 'EPSG:32610' # UTM Zone 10N (适用于美国西海岸)

    # 使用rasterio写入文件
    with rasterio.open(
        filename,
        'w',
        driver='GTiff',
        height=dem_data.shape[0],
        width=dem_data.shape[1],
        count=1, # 单波段
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
    # --- 示例1：生成一个复杂的虚拟DEM ---
    # 这个DEM将包含一座主峰，一座次峰，和一个山谷
    complex_config = {
        'size_pixels': (8000, 8000),         # 5000x5000 像素
        'resolution_m': 1.0,                 # 每个像素代表1米
        'origin_xy': (300000, 4000000),      # 地图左上角的UTM坐标
        'base_elevation': 800.0,             # 基础海拔800米
        'peaks': [
            # 主峰 (高大、宽广)
            {'amplitude': 700, 'center_xy_ratio': (0.5, 0.5), 'sigma_xy_ratio': (0.15, 0.15)},
            # 次峰 (稍矮、陡峭)
            {'amplitude': 450, 'center_xy_ratio': (0.2, 0.7), 'sigma_xy_ratio': (0.08, 0.08)},
            # 山谷 (负振幅)
            {'amplitude': -200, 'center_xy_ratio': (0.8, 0.3), 'sigma_xy_ratio': (0.1, 0.1)}
        ]
    }
    generate_dem(
        filename='./data/complex_virtual_dem.tif', 
        mode='complex', 
        config=complex_config
    )

    print("\n" + "="*50 + "\n")

    # --- 示例2：生成一个简单的、朝向东北方的山坡 ---
    simple_config = {
        'size_pixels': (1000, 1000),
        'resolution_m': 2.0,
        'origin_xy': (500000, 4200000),
        'base_elevation': 1000.0,
        'slope_deg': 25.0,                   # 坡度25度
        'slope_direction_deg': 45.0          # 坡度朝向东北方 (45度)
    }
    generate_dem(
        filename='./data/simple_slope_dem.tif', 
        mode='simple', 
        config=simple_config
    )
