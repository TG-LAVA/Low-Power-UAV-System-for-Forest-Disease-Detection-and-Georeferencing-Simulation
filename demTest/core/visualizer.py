# core/visualizer.py (增强版 - 等高线 + 箭头 + 参考平面)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from matplotlib.colors import LightSource

class Visualizer:
    """
    负责生成可视化输出（2D地图、航线图等）
    """
    def __init__(self, config, results, stats, dem_data, dem_transform):
        self.config = config
        self.results = results
        self.stats = stats
        self.dem_data = dem_data
        self.dem_transform = dem_transform
        
        # 计算DEM的世界坐标边界
        self.dem_bounds = {
            'left': dem_transform.c,
            'bottom': dem_transform.f + dem_transform.e * dem_data.shape[0],
            'right': dem_transform.c + dem_transform.a * dem_data.shape[1],
            'top': dem_transform.f
        }

    def plot_dem_background(self, ax, show_contours=True):
        """
        在给定的axes上绘制DEM背景（带阴影的地形图 + 等高线）
        
        参数:
        - ax: matplotlib axes对象
        - show_contours: 是否显示等高线
        """
        # 创建光照效果
        ls = LightSource(azdeg=315, altdeg=45)
        
        # 计算阴影地形
        shaded = ls.hillshade(
            self.dem_data, 
            vert_exag=2.0,
            dx=abs(self.dem_transform.a),
            dy=abs(self.dem_transform.e)
        )
        
        # 绘制DEM（使用terrain配色方案）
        extent = [
            self.dem_bounds['left'],
            self.dem_bounds['right'],
            self.dem_bounds['bottom'],
            self.dem_bounds['top']
        ]
        
        # 先绘制高程颜色
        im = ax.imshow(
            self.dem_data,
            cmap='terrain',
            extent=extent,
            origin='upper',
            alpha=0.6,
            aspect='equal'
        )
        
        # 叠加阴影效果
        ax.imshow(
            shaded,
            cmap='gray',
            extent=extent,
            origin='upper',
            alpha=0.3,
            aspect='equal'
        )
        
        # ✅ 新增：绘制等高线
        if show_contours:
            # 创建坐标网格
            x = np.linspace(extent[0], extent[1], self.dem_data.shape[1])
            y = np.linspace(extent[3], extent[2], self.dem_data.shape[0])
            X, Y = np.meshgrid(x, y)
            
            # 计算等高线间隔（根据高程范围自动调整）
            z_min, z_max = np.nanmin(self.dem_data), np.nanmax(self.dem_data)
            z_range = z_max - z_min
            contour_interval = max(50, int(z_range / 10))  # 至少50m间隔
            
            # 绘制等高线
            contours = ax.contour(
                X, Y, self.dem_data,
                levels=np.arange(
                    int(z_min / contour_interval) * contour_interval,
                    int(z_max / contour_interval) * contour_interval + contour_interval,
                    contour_interval
                ),
                colors='black',
                linewidths=0.5,
                alpha=0.4
            )
            
            # 每隔一条标注高程值
            ax.clabel(contours, inline=True, fontsize=8, fmt='%d m')
        
        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax, label='Elevation (m)', shrink=0.8)
        
        return im

    def plot_2d_map(self, output_path):
        """
        生成传统的2D投影误差地图（单点或多点）
        """
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # 绘制DEM背景（带等高线）
        self.plot_dem_background(ax, show_contours=True)
        
        # 绘制投影结果 (使用索引判断是否是第一个元素)
        for i, res in enumerate(self.results):
            slope_pt = res['slope_projection']
            planar_pt = res['planar_projection']
            camera_pos = res['camera_pos']
            
            # 真实投影点（绿色）
            ax.plot(slope_pt[0], slope_pt[1], 'go', markersize=8, 
                   label='True (Slope)' if i == 0 else "")
            
            # 平面投影点（红色）
            ax.plot(planar_pt[0], planar_pt[1], 'rx', markersize=8,
                   label='False (Planar)' if i == 0 else "")
            
            # 误差连线
            ax.plot([slope_pt[0], planar_pt[0]], 
                   [slope_pt[1], planar_pt[1]], 
                   'b-', linewidth=1, alpha=0.5)
            
            # 相机位置（蓝色三角）
            ax.plot(camera_pos[0], camera_pos[1], 'b^', markersize=10,
                   label='Camera' if i == 0 else "")
        
        # 设置
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Y (meters)', fontsize=12)
        ax.set_title(f"{self.config['scenario_name']} - Georeferencing Error Visualization\n"
                    f"RMSE = {self.stats['rmse']:.2f} m", fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ 2D map saved: {output_path}")

    def plot_trajectory_map(self, output_path):
        """
        生成航线轨迹可视化地图（专门用于航线模拟）
        增强功能：等高线 + 箭头 + 参考平面标注
        """
        fig, ax = plt.subplots(figsize=(14, 12))
        
        # 绘制DEM背景（带等高线）
        self.plot_dem_background(ax, show_contours=True)
        
        # ✅ 计算参考平面高程（从planar_projection的Z值获取）
        if self.results:
            reference_elevations = [res.get('planar_projection', [0, 0, 0])[2] 
                                   for res in self.results 
                                   if len(res.get('planar_projection', [])) > 2]
            if reference_elevations:
                ref_z = np.mean(reference_elevations)
                # 在标题中显示参考平面高程
                ref_plane_text = f"Reference Plane: Z={ref_z:.1f}m"
            else:
                ref_plane_text = ""
        else:
            ref_plane_text = ""
        
        # 提取所有相机位置
        camera_positions = []
        waypoint_indices = []
        for res in self.results:
            cam_pos = res['camera_pos']
            waypoint_idx = res.get('waypoint_index', 0)
            
            if not any(np.array_equal(cam_pos, cp) for cp in camera_positions):
                camera_positions.append(cam_pos)
                waypoint_indices.append(waypoint_idx)
        
        # 绘制航线（蓝色虚线）
        if len(camera_positions) > 1:
            cam_x = [pos[0] for pos in camera_positions]
            cam_y = [pos[1] for pos in camera_positions]
            ax.plot(cam_x, cam_y, 'b--', linewidth=2, alpha=0.7, label='Flight Path')
        
        # 绘制相机位置（蓝色三角）
        for i, pos in enumerate(camera_positions):
            ax.plot(pos[0], pos[1], 'b^', markersize=10, 
                   label='Camera Position' if i == 0 else "")
            # 添加航点编号
            ax.text(pos[0], pos[1] + 20, f'#{waypoint_indices[i]+1}', 
                   fontsize=8, ha='center', color='blue',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
        
        # ✅ 修复：使用索引判断 + 标志变量控制图例
        label_flags = {
            'true': False,
            'planar': False,
            'error': False
        }
        
        # 绘制每个检测点的投影结果
        for i, res in enumerate(self.results):
            slope_pt = res['slope_projection']
            planar_pt = res['planar_projection']
            error = res['error_m']
            
            # 真实投影点（绿色圆点）
            true_label = 'True Projection (Slope)' if not label_flags['true'] else ""
            ax.plot(slope_pt[0], slope_pt[1], 'go', markersize=6, alpha=0.7,
                   label=true_label, zorder=5)
            if not label_flags['true']:
                label_flags['true'] = True
            
            # 平面投影点（红色叉）
            planar_label = 'Planar Projection' if not label_flags['planar'] else ""
            ax.plot(planar_pt[0], planar_pt[1], 'rx', markersize=6, alpha=0.7,
                   label=planar_label, zorder=5)
            if not label_flags['planar']:
                label_flags['planar'] = True
            
            # ✅ 新增：用箭头代替虚线表示误差方向
            error_label = 'Projection Error' if not label_flags['error'] else ""
            
            # 创建箭头（从红叉指向绿点，表示"平面假设的偏移"）
            arrow = FancyArrowPatch(
                (planar_pt[0], planar_pt[1]),  # 起点：错误位置
                (slope_pt[0], slope_pt[1]),    # 终点：正确位置
                arrowstyle='-|>',
                mutation_scale=15,
                linewidth=1.5,
                color='red',
                alpha=0.6,
                label=error_label,
                zorder=4
            )
            ax.add_patch(arrow)
            
            if not label_flags['error']:
                label_flags['error'] = True
            
            # 在箭头中点标注误差值（对于较大误差）
            if error > self.stats['mean']:
                mid_x = (slope_pt[0] + planar_pt[0]) / 2
                mid_y = (slope_pt[1] + planar_pt[1]) / 2
                ax.text(mid_x, mid_y, f"{error:.1f}m", 
                       fontsize=7, color='red', ha='center',
                       bbox=dict(boxstyle='round,pad=0.2', 
                                facecolor='yellow', alpha=0.7),
                       zorder=6)
        
        # 设置标题（包含参考平面信息）
        title_text = (
            f"{self.config['scenario_name']} - Trajectory Simulation Results\n"
            f"Total Waypoints: {len(camera_positions)} | "
            f"Detections: {len(self.results)} | "
            f"RMSE: {self.stats['rmse']:.2f}m | "
            f"Mean Error: {self.stats['mean']:.2f}m"
        )
        
        if ref_plane_text:
            title_text += f"\n{ref_plane_text}"
        
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Y (meters)', fontsize=12)
        ax.set_title(title_text, fontsize=14)
        
        # 图例
        ax.legend(loc='upper left', fontsize=10)
        
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"   ✅ Trajectory map saved: {output_path}")
