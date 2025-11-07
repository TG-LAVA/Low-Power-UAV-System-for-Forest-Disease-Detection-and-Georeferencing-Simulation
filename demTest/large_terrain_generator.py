# create_terrain_asset.py

import os
import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.ndimage import gaussian_filter

# ==============================================================================
# --- 您可以在这里修改配置 ---
# ==============================================================================
TERRAIN_CONFIG = {
    # --- 核心参数 ---
    "size_km": 20,           # 地形正方形边长 (公里)
    "resolution_m": 2,       # 分辨率 (米/像素)
    
    # --- 地貌参数 ---
    "base_elevation_m": 500, # 基础海拔 (米)
    "relief_m": 1500,        # 最大地势起伏 (米)，决定山脉的相对高度
    
    # --- 随机性控制 ---
    "seed": 42,              # 随机种子，使用相同种子可生成完全相同的地形
    
    # --- 文件输出 ---
    "output_dir": "data", # 输出文件夹名称
    "filename_prefix": "large_virtual_dem" # 文件名前缀
}
# ==============================================================================


def generate_perlin_noise_2d(shape, res):
    """
    生成2D Perlin噪声，用于辅助效果。
    """
    def fade(t): return 6 * t**5 - 15 * t**4 + 10 * t**3
    
    grid_y, grid_x = np.mgrid[0:shape[0], 0:shape[1]]
    scaled_x = grid_x * (res[1] / shape[1])
    scaled_y = grid_y * (res[0] / shape[0])
    
    ix0, iy0 = np.floor(scaled_x).astype(int), np.floor(scaled_y).astype(int)
    ix1, iy1 = ix0 + 1, iy0 + 1
    
    fx, fy = scaled_x - ix0, scaled_y - iy0
    
    angles = 2 * np.pi * np.random.rand(res[0] + 1, res[1] + 1)
    gradients = np.dstack((np.cos(angles), np.sin(angles)))
    
    g00 = gradients[iy0 % res[0], ix0 % res[1]]
    g10 = gradients[iy1 % res[0], ix0 % res[1]]
    g01 = gradients[iy0 % res[0], ix1 % res[1]]
    g11 = gradients[iy1 % res[0], ix1 % res[1]]
    
    v00 = np.dstack((fx, fy)); v10 = np.dstack((fx - 1, fy))
    v01 = np.dstack((fx, fy - 1)); v11 = np.dstack((fx - 1, fy - 1))
    
    n00 = np.sum(g00 * v00, axis=-1); n10 = np.sum(g10 * v10, axis=-1)
    n01 = np.sum(g01 * v01, axis=-1); n11 = np.sum(g11 * v11, axis=-1)

    t = fade(np.dstack((fx, fy))); tx, ty = t[..., 0], t[..., 1]
    
    n0 = n00 * (1 - tx) + n10 * tx
    n1 = n01 * (1 - tx) + n11 * tx
    noise = (1 - ty) * n0 + ty * n1
    
    return (noise - noise.min()) / (noise.max() - noise.min())


def create_terrain(config):
    """
    核心函数：根据配置生成并保存一个大规模地形GeoTIFF文件。
    """
    # --- 1. 解包配置并设置随机种子 ---
    size_km = config["size_km"]
    resolution_m = config["resolution_m"]
    base_elevation = config["base_elevation_m"]
    relief = config["relief_m"]
    seed = config["seed"]
    output_dir = config["output_dir"]
    
    if seed is not None:
        np.random.seed(seed)
    
    # --- 2. 计算尺寸和文件名 ---
    size_pixels = int(size_km * 1000 / resolution_m)
    filename = f"{config['filename_prefix']}_{size_km}km_{resolution_m}m_seed{seed}.tif"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_path = os.path.join(output_dir, filename)

    print("="*60)
    print(f"🏔️  Generating New Terrain Asset")
    print(f"   - Config: {size_km}km size, {resolution_m}m resolution, seed={seed}")
    print(f"   - Grid: {size_pixels} x {size_pixels} pixels")
    print(f"   - Output: {output_path}")
    
    # --- 3. 生成地形 (高斯叠加法) ---
    xx, yy = np.meshgrid(
        np.linspace(0, size_pixels - 1, size_pixels),
        np.linspace(0, size_pixels - 1, size_pixels)
    )
    dem_data = np.full((size_pixels, size_pixels), float(base_elevation), dtype=np.float32)

    # 定义多尺度地貌特征
    feature_scales = {
        'main_ranges':     (10, 0.7 * relief, 1.0 * relief, 0.15, 0.25),
        'secondary_peaks': (30, 0.3 * relief, 0.6 * relief, 0.05, 0.12),
        'hills':           (100, 0.05 * relief, 0.25 * relief, 0.02, 0.06),
        'valleys':         (25, -0.4 * relief, -0.1 * relief, 0.04, 0.10)
    }

    print("\n   - Adding geological features...")
    for name, params in feature_scales.items():
        count, min_amp, max_amp, min_sigma_r, max_sigma_r = params
        amplitudes = np.random.uniform(min_amp, max_amp, count)
        center_x = np.random.uniform(0, size_pixels, count)
        center_y = np.random.uniform(0, size_pixels, count)
        sigma_x = np.random.uniform(min_sigma_r * size_pixels, max_sigma_r * size_pixels, count)
        sigma_y = sigma_x * np.random.uniform(0.7, 1.3, count)
        
        for i in range(count):
            amp, cx, cy, sx, sy = amplitudes[i], center_x[i], center_y[i], sigma_x[i], sigma_y[i]
            exponent = -(((xx - cx)**2 / (2 * sx**2)) + ((yy - cy)**2 / (2 * sy**2)))
            dem_data += amp * np.exp(exponent)

    # --- 4. 应用后期处理 (侵蚀 & 平滑) ---
    print("   - Applying erosion and smoothing...")
    erosion_noise = generate_perlin_noise_2d((size_pixels, size_pixels), res=(64, 64))
    dem_data += (erosion_noise - 0.5) * (0.05 * relief)
    dem_data = gaussian_filter(dem_data, sigma=2)
    dem_data = dem_data.astype(np.float32)

    # --- 5. 保存为带地理参考的GeoTIFF文件 ---
    print("   - Writing to GeoTIFF file...")
    origin_x = 300000
    origin_y = 4000000 + size_km * 1000
    transform = from_origin(origin_x, origin_y, resolution_m, resolution_m)
    crs = 'EPSG:32610'

    with rasterio.open(
        output_path, 'w', driver='GTiff', height=dem_data.shape[0],
        width=dem_data.shape[1], count=1, dtype=dem_data.dtype,
        crs=crs, transform=transform
    ) as dst:
        dst.write(dem_data, 1)

    print("\n   ✅ Generation Complete!")
    print(f"      -> Elevation Range: [{dem_data.min():.1f}, {dem_data.max():.1f}] m")
    print("="*60)
    
if __name__ == "__main__":
    # 确保已安装所需库: pip install numpy rasterio scipy
    try:
        import scipy
    except ImportError:
        print("\nError: 'scipy' library not found.")
        print("Please install it by running: pip install scipy\n")
        exit()

    # --- 执行生成 ---
    create_terrain(TERRAIN_CONFIG)
    
    # --- 示例：如果您想一次性生成多个，可以这样做 ---
    # print("\nStarting batch generation...")
    # 
    # config_1 = TERRAIN_CONFIG.copy()
    # config_1["size_km"] = 10
    # config_1["resolution_m"] = 5
    # create_terrain(config_1)
    # 
    # config_2 = TERRAIN_CONFIG.copy()
    # config_2["size_km"] = 30
    # config_2["resolution_m"] = 5
    # config_2["relief_m"] = 2000 # 更高的山
    # create_terrain(config_2)

