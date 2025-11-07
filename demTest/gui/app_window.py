# gui/app_window.py (修复版)

import numpy as np

from PyQt6.QtWidgets import QMainWindow, QSplitter, QStatusBar
from PyQt6.QtCore import Qt, QThreadPool

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LightSource

from .state_manager import StateManager
from .backend_service import BackendService
from .widgets.control_panel import ControlPanel
from .worker import Worker

class AppWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        
        self.threadpool = QThreadPool()
        print(f"UI: Multithreading enabled with up to {self.threadpool.maxThreadCount()} threads.")
       
        print("UI: Initializing StateManager and BackendService...")
        self.state = StateManager(config)
        self.backend = BackendService(self.state)
        
        # 1. 先注册回调
        # self.state.register_update_callback(self.trigger_recalculation)
        
        self.drawing_points = []
        self.map_click_connection = None
        
        self.current_simulation_data = {
            'results': [],
            'stats': {'rmse': 0, 'mean': 0, 'max': 0, 'min': 0, 'count': 0},
            'dem_data': None,
            'dem_transform': None
        }
        
        # 2. 初始化UI
        self._init_ui()
        
        # 3. 获取对按钮的引用
        self.run_sim_button = self.control_panel.run_sim_button
        self.control_panel.parent_window = self # 用于导出
        
        # 4. 连接信号
        self._connect_ui_signals()
        
        # 5. 加载初始视图
        print("UI: Loading initial map view (no simulation)...")
        self._load_initial_dem()
        self.draw_2d_map()
        self.draw_3d_view()
        
        # ✅ 核心修复: 在所有UI组件都已创建并连接好之后，才将StateManager设为就绪状态
        self.state.set_ready()
        
        print("UI: Ready. User interaction will now trigger calculations.")
    def _load_initial_dem(self):
        """只加载DEM数据，不进行模拟计算"""
        try:
            from core.data_loader import DataLoader
            from core.dem_generator import create_slope_dem

            
            if self.state.current_scene == "virtual_slope":
                dem_data, dem_transform = create_slope_dem(
                    slope_deg=self.state.virtual_slope_angle
                )
            elif self.state.current_scene == "large_terrain":
                dem_data, dem_transform = DataLoader.load_dem(self.state.dem_path_large)
            else:
                dem_data, dem_transform = DataLoader.load_dem(self.state.dem_path_complex)
            
            # 更新数据
            self.current_simulation_data['dem_data'] = dem_data
            self.current_simulation_data['dem_transform'] = dem_transform
            
            print(f"   ✅ Initial DEM loaded: {dem_data.shape if dem_data is not None else 'None'}")
            
        except Exception as e:
            print(f"   ❌ Error loading DEM: {e}")
            import traceback
            traceback.print_exc()

    def _init_ui(self):
        self.setWindowTitle("GEVS-GUI: Terrain Slope's Impact on Aerial Survey Projection Error - Interactive Simulator")
        self.setGeometry(100, 100, 1800, 1000)
        
        self.control_panel = ControlPanel(self.state)
        self.canvas_2d = FigureCanvas(Figure(figsize=(10, 10), tight_layout=True))
        self.ax_2d = self.canvas_2d.figure.subplots()
        self.canvas_3d = FigureCanvas(Figure(figsize=(10, 10), tight_layout=True))
        self.ax_3d = self.canvas_3d.figure.add_subplot(111, projection='3d')
        
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        view_splitter = QSplitter(Qt.Orientation.Vertical)
        view_splitter.addWidget(self.canvas_2d)
        view_splitter.addWidget(self.canvas_3d)
        view_splitter.setSizes([400, 600])

        main_splitter.addWidget(view_splitter)
        main_splitter.addWidget(self.control_panel)
        main_splitter.setSizes([1350, 450])
        
        self.setCentralWidget(main_splitter)
        self.setStatusBar(QStatusBar(self))

    def trigger_recalculation(self):
        print("UI: 'Run Simulation' button clicked. Preparing to run...")
        
        # ✅ 关键修复：在运行前，从UI收集所有最新状态，包括可视化选项
        print("   -> Collecting latest UI states...")
        
        # 收集单点模式参数
        if self.state.simulation_mode == 'single_point':
            self.state.update_state(
                camera_position=[
                    self.control_panel.pos_x.value(), 
                    self.control_panel.pos_y.value(), 
                    self.control_panel.pos_z.value()
                ],
                camera_attitude={
                    'roll': self.control_panel.roll.value(), 
                    'pitch': self.control_panel.pitch.value(), 
                    'yaw': self.control_panel.yaw.value()
                },
                trigger_recalc=False # 避免重复触发
            )
        
        # 收集可视化参数（对所有模式都适用）
        self.state.update_state(
            show_camera_coverage=self.control_panel.show_coverage_check.isChecked(),
            show_ref_plane_in_3d=self.control_panel.show_ref_plane_check.isChecked(),
            trigger_recalc=False # 避免重复触发
        )
        
        # --- 后续代码保持不变 ---
        print("UI: Triggering async recalculation...")
        self.run_sim_button.setText("🔄 Calculating...")
        self.run_sim_button.setEnabled(False)
        worker = Worker(self.backend.run_simulation_for_state, self.state)
        worker.signals.result.connect(self.handle_calculation_result)
        worker.signals.finished.connect(self.on_calculation_finished)
        worker.signals.error.connect(self.on_calculation_error)
        self.threadpool.start(worker)

    def handle_calculation_result(self, data):
        print("UI: Calculation result received. Updating data and starting redraw...")
        self.current_simulation_data = data
        self.control_panel.update_results(data)
        if self.current_simulation_data and self.current_simulation_data.get('dem_data') is not None:
            self.draw_2d_map()
            self.draw_3d_view()
            print("UI: Redraw complete.")
        else:
            print("UI: Received invalid data packet. Skipping redraw.")

    def _connect_ui_signals(self):
        self.control_panel.run_simulation_requested.connect(self.trigger_recalculation)
        self.control_panel.draw_trajectory_requested.connect(self.enter_drawing_mode)
        self.control_panel.scene_changed_requested.connect(self._on_scene_changed)
    def enter_drawing_mode(self):
        if self.map_click_connection is not None:
            self.exit_drawing_mode()
            return

        self.state.update_state(is_drawing_trajectory=True, trigger_recalc=False)
        self.drawing_points = []
        self.statusBar().showMessage("Draw Mode: Click on the 2D map to select the [Start Point].", 5000)
        self.map_click_connection = self.canvas_2d.mpl_connect('button_press_event', self.on_map_click)
    
    def exit_drawing_mode(self):
        if self.map_click_connection:
            self.canvas_2d.mpl_disconnect(self.map_click_connection)
            self.map_click_connection = None
        self.state.update_state(is_drawing_trajectory=False, trigger_recalc=False)
        self.statusBar().clearMessage()

    def on_map_click(self, event):
        if event.inaxes != self.ax_2d:
            return
        
        x, y = event.xdata, event.ydata
        self.drawing_points.append({'x': x, 'y': y})
        
        if len(self.drawing_points) == 1:
            self.statusBar().showMessage(f"Start point selected ({x:.1f}, {y:.1f}). Click to select the [End Point].", 5000)
            self.ax_2d.plot(x, y, 'm+', markersize=15, markeredgewidth=2)
            # self.canvas_2d.draw()
        elif len(self.drawing_points) == 2:
            self.statusBar().showMessage(f"End point selected  ({x:.1f}, {y:.1f}). Trajectory updated.", 3000)
            self.state.update_state(trajectory_path=self.drawing_points, trigger_recalc=False)
            self.control_panel.update_controls_from_state()
            # self.exit_drawing_mode()
            # self.draw_2d_map()

    def on_calculation_finished(self):
        print("UI: Async calculation job finished.")
        self.run_sim_button.setText("🚀 Run Simulation")
        self.run_sim_button.setEnabled(True)
        
    def on_calculation_error(self, err_tuple):
        print(f"❌ FATAL ERROR in worker thread: {err_tuple[1]}")
        self.run_sim_button.setText("⚠️ Error, please try again")
        self.run_sim_button.setEnabled(True)

    def _draw_dem_background(self, ax, dem_data, dem_transform):
        """绘制DEM背景（带高程渲染和等高线）"""
        if dem_data is None or dem_transform is None:
            return

        left, bottom, right, top = (
            dem_transform.c, 
            dem_transform.f + dem_transform.e * dem_data.shape[0], 
            dem_transform.c + dem_transform.a * dem_data.shape[1], 
            dem_transform.f
        )
        extent = [left, right, bottom, top]

        ls = LightSource(azdeg=315, altdeg=45)
        shaded = ls.hillshade(dem_data, vert_exag=1.5, dx=abs(dem_transform.a), dy=abs(dem_transform.e))
        ax.imshow(dem_data, cmap='terrain', extent=extent, origin='upper', alpha=0.6)
        ax.imshow(shaded, cmap='gray', extent=extent, origin='upper', alpha=0.4)

        x = np.linspace(extent[0], extent[1], dem_data.shape[1])
        y = np.linspace(extent[3], extent[2], dem_data.shape[0])
        X, Y = np.meshgrid(x, y)
        z_min, z_max = np.nanmin(dem_data), np.nanmax(dem_data)
        
        if z_max - z_min < 1e-6: 
            return
        
        levels = np.linspace(z_min, z_max, 15)
        try:
            contours = ax.contour(X, Y, dem_data, levels=levels, colors='black', linewidths=0.5, alpha=0.5)
            ax.clabel(contours, inline=True, fontsize=8, fmt='%d m')
        except Exception as e:
            print(f"⚠️ Warning: matplotlib contour/clabel failed: {e}.")

    def draw_2d_map(self):
        """绘制2D地图视图"""
        self.ax_2d.clear()
        
        # ✅ 安全地获取数据
        dem_data = self.current_simulation_data.get('dem_data')
        dem_transform = self.current_simulation_data.get('dem_transform')
        results = self.current_simulation_data.get('results', [])
        stats = self.current_simulation_data.get('stats', {})

        # 绘制DEM背景
        self._draw_dem_background(self.ax_2d, dem_data, dem_transform)

        self.ax_2d.set_title("2D Projection Error Analysis")
        self.ax_2d.set_xlabel("World Coordinate X (m)")
        self.ax_2d.set_ylabel("World Coordinate Y (m)")
        self.ax_2d.set_aspect('equal', adjustable='box')
        self.ax_2d.grid(True, linestyle='--', alpha=0.3)

        # ✅ 如果没有模拟结果，显示提示信息
        if not results:
            hint_msg = "Map Loaded\n\nClick 'Run Simulation' to start"
            self.ax_2d.text(0.5, 0.5, hint_msg, ha='center', va='center', 
                        transform=self.ax_2d.transAxes, fontsize=12,
                        bbox=dict(boxstyle='round,pad=1', facecolor='lightblue', alpha=0.8))
            self.canvas_2d.draw()
            return

        # 绘制相机位置和航线
        if self.state.simulation_mode == 'trajectory':
            unique_cam_pos = {tuple(res['camera_pos']): res.get('waypoint_index', 0) for res in results}
            sorted_cam_pos = sorted(unique_cam_pos.items(), key=lambda item: item[1])
            camera_positions = [np.array(pos) for pos, idx in sorted_cam_pos]
            if len(camera_positions) > 1:
                self.ax_2d.plot([p[0] for p in camera_positions], [p[1] for p in camera_positions], 
                            'b--', lw=1.5, alpha=0.8, label='Trajectory')
            for i, pos in enumerate(camera_positions):
                self.ax_2d.plot(pos[0], pos[1], 'b^', markersize=8, 
                            label='Camera Position' if i == 0 else "")
        else:
            if results: 
                cam_pos = results[0]['camera_pos']
                self.ax_2d.plot(cam_pos[0], cam_pos[1], 'b^', markersize=10, label='Camera Position')

        # 绘制相机覆盖范围
        if self.state.show_camera_coverage and results:
            self._draw_camera_coverage(self.ax_2d, results)

        # 绘制投影点和误差线
        for i, res in enumerate(results):
            p_true, p_false = res['slope_projection'], res['planar_projection']
            self.ax_2d.plot(p_true[0], p_true[1], 'go', markersize=4, 
                        label='Terrain Projection (True)' if i == 0 else "")
            self.ax_2d.plot(p_false[0], p_false[1], 'rx', markersize=5, 
                        label='Planar Projection (Error)' if i == 0 else "")
            self.ax_2d.annotate("", xy=(p_true[0], p_true[1]), xytext=(p_false[0], p_false[1]),
                            arrowprops=dict(arrowstyle="->", color='r', lw=1.0, shrinkA=0, shrinkB=0))

        # 统计信息
        stats_text = (f"RMSE: {stats.get('rmse', 0):.2f} m\n"
                     f"Mean: {stats.get('mean', 0):.2f} m\n"
                     f"Max: {stats.get('max', 0):.2f} m")
        self.ax_2d.text(0.98, 0.98, stats_text, transform=self.ax_2d.transAxes, fontsize=10,
                        verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.6))
        
        self.ax_2d.legend()
        self.canvas_2d.draw()

    def draw_3d_view(self):
        """绘制3D空间视图"""
        self.ax_3d.clear()
        
        # ✅ 安全地获取数据
        dem_data = self.current_simulation_data.get('dem_data')
        dem_transform = self.current_simulation_data.get('dem_transform')
        results = self.current_simulation_data.get('results', [])
        
        if dem_data is None:
            self.ax_3d.text(0.5, 0.5, 0.5, 'Waiting for DEM data...', 
                        ha='center', va='center', transform=self.ax_3d.transAxes)
            self.canvas_3d.draw()
            return
        
        # 降采样DEM以提高性能
        rows, cols = dem_data.shape
        step = max(1, rows // 100, cols // 100)
        dem_sampled = dem_data[::step, ::step]
        rows_s, cols_s = dem_sampled.shape
        
        # 创建坐标网格
        row_indices, col_indices = np.indices((rows_s, cols_s))
        row_indices *= step
        col_indices *= step
        
        x_coords, y_coords = dem_transform * (col_indices, row_indices)

        x_min, x_max = np.min(x_coords), np.max(x_coords)
        y_min, y_max = np.min(y_coords), np.max(y_coords)
        z_min, z_max = np.nanmin(dem_sampled), np.nanmax(dem_sampled)
        
        # 绘制地形表面
        self.ax_3d.plot_surface(
            x_coords, y_coords, dem_sampled,
            cmap='terrain', alpha=0.7, linewidth=0, antialiased=True
        )
        
        # 绘制参考平面（如果有模拟结果）
        if self.state.show_ref_plane_in_3d and results:
            ref_elevation = None
            
            # 1. 根据模式确定参考高程
            if self.state.ref_elevation_mode == "custom_value":
                ref_elevation = self.state.custom_ref_elevation
                plane_label = f'Custom Reference Plane (Z={ref_elevation:.1f}m)'
            elif self.state.ref_elevation_mode == "camera_nadir":
                # 在nadir模式下，参考高程是每个点独立计算的，
                # 为了可视化，我们取所有平面投影点的Z值平均值。
                planar_z_values = [res['planar_projection'][2] for res in results]
                if planar_z_values:
                    ref_elevation = np.mean(planar_z_values)
                    plane_label = f'Camera Nadir Reference Plane (Avg Z≈{ref_elevation:.1f}m)'
            
            # 2. 如果成功获取了参考高程，则绘制
            if ref_elevation is not None:
                plane_x = np.linspace(x_min, x_max, 2)
                plane_y = np.linspace(y_min, y_max, 2)
                plane_xx, plane_yy = np.meshgrid(plane_x, plane_y)
                plane_zz = np.full_like(plane_xx, ref_elevation)
                
                self.ax_3d.plot_surface(
                    plane_xx, plane_yy, plane_zz,
                    color='cyan', alpha=0.2, linewidth=0, antialiased=True
                )
                
                # 3. 添加标签
                center_x = (x_min + x_max) / 2
                center_y = (y_min + y_max) / 2
                
                self.ax_3d.text(
                    center_x, center_y, ref_elevation,
                    plane_label,  # 使用动态生成的标签
                    color='blue', fontsize=9, ha='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
                )
        
        # 绘制相机、投影点、视线和误差线
        if results:
            camera_positions = {tuple(res['camera_pos']): res for res in results}
            
            first_camera = True
            for cam_pos_tuple, res in camera_positions.items():
                cam_pos = np.array(cam_pos_tuple)
                self.ax_3d.scatter(
                    [cam_pos[0]], [cam_pos[1]], [cam_pos[2]], 
                    c='blue', marker='^', s=150, 
                    label='Camera Position' if first_camera else ""
                )
                first_camera = False

            slope_points = np.array([r['slope_projection'] for r in results])
            planar_points = np.array([r['planar_projection'] for r in results])
            
            self.ax_3d.scatter(slope_points[:, 0], slope_points[:, 1], slope_points[:, 2],
                            c='green', marker='o', s=50, alpha=0.7, label='Terrain Projection (True)')
            self.ax_3d.scatter(planar_points[:, 0], planar_points[:, 1], planar_points[:, 2],
                            c='red', marker='x', s=50, alpha=0.7, label='Planar Projection (Error)')
            
            # 只绘制前10条线
            for i, res in enumerate(results[:10]):
                cam_pos = res['camera_pos']
                slope_pt = res['slope_projection']
                planar_pt = res['planar_projection']
                
                self.ax_3d.plot([cam_pos[0], slope_pt[0]], 
                            [cam_pos[1], slope_pt[1]], 
                            [cam_pos[2], slope_pt[2]], 
                            'b--', alpha=0.3, linewidth=0.5)
                self.ax_3d.plot([slope_pt[0], planar_pt[0]], 
                            [slope_pt[1], planar_pt[1]], 
                            [slope_pt[2], planar_pt[2]], 
                            'r-', alpha=0.5, linewidth=1)
        
        # 设置坐标轴
        self.ax_3d.set_xlim(x_min, x_max)
        self.ax_3d.set_ylim(y_min, y_max)
        
        z_range_min = z_min
        z_range_max = z_max
        if results and self.state.show_ref_plane_in_3d:
            ref_elevation = results[0]['planar_projection'][2]
            z_range_min = min(z_min, ref_elevation)
            z_range_max = max(z_max, ref_elevation)
        
        z_margin = (z_range_max - z_range_min) * 0.1
        self.ax_3d.set_zlim(z_range_min - z_margin, z_range_max + z_margin)
        
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Elevation (m)')
        self.ax_3d.set_title('3D Spatial Geometry')
        
        # 添加图例
        handles, labels = self.ax_3d.get_legend_handles_labels()
        if labels:
            by_label = dict(zip(labels, handles))
            self.ax_3d.legend(by_label.values(), by_label.keys(), loc='upper left', fontsize=8)
        
        self.canvas_3d.draw()

    # gui/app_window.py

    # gui/app_window.py

    def _draw_camera_coverage(self, ax, results):
        """✅ 修复版：在2D视图中绘制相机的地面覆盖范围"""
        from matplotlib.patches import Polygon
        
        if not results:
            return
        
        # 分组相机位置
        unique_cameras = {}
        for res in results:
            cam_pos_tuple = tuple(res['camera_pos'])
            if cam_pos_tuple not in unique_cameras:
                unique_cameras[cam_pos_tuple] = res
        
        for i, (cam_pos_tuple, res) in enumerate(unique_cameras.items()):
            from core.camera_model import CameraModel
            
            camera_pos = np.array(cam_pos_tuple)
            
            # --- 根据模式选择正确的姿态参数 ---
            if self.state.simulation_mode == 'trajectory':
                attitude = self.state.trajectory_attitude
                yaw = attitude.get('yaw', 0.0)
                
                # ✅ 关键修复 1：修正自动偏航计算
                if isinstance(attitude.get('yaw'), str) and attitude['yaw'].lower() == 'auto':
                    path = self.state.trajectory_path
                    if len(path) >= 2:
                        start_node = path[0]
                        end_node = path[1]
                        dx = end_node['x'] - start_node['x']
                        dy = end_node['y'] - start_node['y']
                        # 正确的偏航角计算，从Y轴正向（北）开始，顺时针为正
                        # atan2(dx, dy)
                        yaw = np.degrees(np.arctan2(dx, dy))
                    else:
                        yaw = 0.0
                
                rotation_degrees = {
                    'roll': attitude.get('roll', 0.0),
                    'pitch': attitude.get('pitch', -30.0),
                    'yaw': yaw
                }
            else:
                rotation_degrees = self.state.camera_attitude
            
            # --- 获取真实的地面高程 ---
            ground_elevation = self._get_ground_elevation_at(camera_pos[0], camera_pos[1])
            if ground_elevation is None:
                ground_elevation = res['planar_projection'][2]
            
            # --- 构建相机参数 ---
            camera_params = {
                'camera_intrinsics': {
                    'focal_length_px': self.state.focal_length_px,
                    'sensor_size_px': self.state.sensor_size_px,
                    'principal_point_px': [
                        self.state.sensor_size_px[0] / 2.0,
                        self.state.sensor_size_px[1] / 2.0
                    ]
                },
                'camera_extrinsics': {
                    'position_meters': camera_pos.tolist(),
                    'rotation_degrees': rotation_degrees
                }
            }
            
            camera = CameraModel(camera_params)
            footprint, _ = camera.compute_ground_coverage(ground_elevation)
            
            if footprint and len(footprint) == 4:
                polygon = Polygon(
                    footprint, closed=True,
                    edgecolor='blue', facecolor='cyan',
                    alpha=0.15, linewidth=2, linestyle='--',
                    label='Camera Coverage' if i == 0 else ""
                )
                ax.add_patch(polygon)
                
                center_x = np.mean([p[0] for p in footprint])
                center_y = np.mean([p[1] for p in footprint])
                
                try:
                    from shapely.geometry import Polygon as ShapelyPolygon
                    poly_shape = ShapelyPolygon(footprint)
                    area_hectare = poly_shape.area / 10000
                    
                    ax.text(
                        center_x, center_y, f'{area_hectare:.1f} ha',
                        fontsize=8, ha='center', va='center', color='blue',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
                    )
                except ImportError:
                    pass

    # gui/app_window.py

    def _get_ground_elevation_at(self, x, y):
        """
        ✅ 新增：获取指定世界坐标的地面高程
        
        Args:
            x, y: 世界坐标
        
        Returns:
            elevation: 地面高程（米），失败返回None
        """
        dem_data = self.current_simulation_data.get('dem_data')
        dem_transform = self.current_simulation_data.get('dem_transform')
        
        if dem_data is None or dem_transform is None:
            return None
        
        try:
            # 世界坐标 → 像素坐标
            col, row = ~dem_transform * (x, y)
            row_int, col_int = int(row), int(col)
            
            # 边界检查
            if 0 <= row_int < dem_data.shape[0] and 0 <= col_int < dem_data.shape[1]:
                return float(dem_data[row_int, col_int])
        except Exception as e:
            print(f"   ⚠️ Warning: Failed to get elevation at ({x:.1f}, {y:.1f}): {e}")
        
        return None
                
    def export_2d_chart(self, file_path, dpi=300):
        """
        导出2D地图图表
        
        Args:
            file_path: 保存路径
            dpi: 图像分辨率（默认300）
        """
        try:
            self.canvas_2d.figure.savefig(
                file_path, 
                dpi=dpi, 
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none',
                transparent=False
            )
            print(f"✅ 2D map exported: {file_path}")
        except Exception as e:
            print(f"❌ Error exporting 2D chart: {e}")

    def export_3d_chart(self, file_path, dpi=300):
        """
        导出3D视图图表
        
        Args:
            file_path: 保存路径
            dpi: 图像分辨率（默认300）
        """
        try:
            self.canvas_3d.figure.savefig(
                file_path,
                dpi=dpi,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none',
                transparent=False
            )
            print(f"✅ 3D view exported: {file_path}")
        except Exception as e:
            print(f"❌ Error exporting 3D chart: {e}")

    def export_combined_report(self, output_dir, dpi=300):
        """
        导出完整报告（图表 + 数据）
        
        Args:
            output_dir: 输出目录
            dpi: 图像分辨率
        """
        import os
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 1. 导出2D地图
            map_2d_path = os.path.join(output_dir, f"2D_map_{timestamp}.png")
            self.export_2d_chart(map_2d_path, dpi)
            
            # 2. 导出3D视图
            view_3d_path = os.path.join(output_dir, f"3D_view_{timestamp}.png")
            self.export_3d_chart(view_3d_path, dpi)
            
            # 3. 导出数据（如果有）
            if self.current_simulation_data and self.current_simulation_data.get('results'):
                import json
                data_path = os.path.join(output_dir, f"data_{timestamp}.json")
                
                export_data = {
                    'metadata': {
                        'export_time': datetime.now().isoformat(),
                        'simulation_mode': self.state.simulation_mode,
                        'scene': self.state.current_scene
                    },
                    'statistics': self.current_simulation_data['stats'],
                    'results': self.current_simulation_data['results']
                }
                
                with open(data_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Complete report exported to: {output_dir}")
            return True
            
        except Exception as e:
            print(f"❌ Error exporting combined report: {e}")
            return False
        
    def _on_scene_changed(self):
        """
        ✅ 新增: 响应ControlPanel的场景切换事件。
        此方法只重新加载和显示新的DEM背景，不运行模拟。
        """
        print("UI: Scene changed. Reloading DEM background...")
        # 清空旧的模拟结果，因为场景已经变了
        self.current_simulation_data['results'] = []
        self.current_simulation_data['stats'] = {'rmse': 0, 'mean': 0, 'max': 0, 'min': 0, 'count': 0}
        
        # 通知控制面板清空导出状态
        self.control_panel.update_results(self.current_simulation_data)
        
        # 重新加载新的DEM
        self._load_initial_dem()
        
        # 重绘视图以显示新的DEM
        self.draw_2d_map()
        self.draw_3d_view()
        print("UI: New DEM background loaded and displayed.")