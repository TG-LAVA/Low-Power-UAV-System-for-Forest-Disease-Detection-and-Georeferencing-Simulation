# gui/state_manager.py (Part B - 多文件支持版)

import json
import os

class StateManager:
    def __init__(self, config):
        print("StateManager: Initializing with config...")
        self.config = config
        
        # --- 数据路径 ---
        data_paths = config.get('data_paths', {})
        self.dem_path_complex = data_paths.get('dem_file', '')
        self.dem_path_large = data_paths.get('dem_large_file', '')
        self.yolo_dataset_dir = data_paths.get('yolo_dataset_dir', '')
        self.camera_config_path = data_paths.get('camera_params_file', '')
        self._is_ready = False
        # --- 场景与模式 ---
        self.current_scene = "complex_terrain"
        self.virtual_slope_angle = 15.0
        self.yolo_association_mode = "cycle"
        # 根据config.json决定初始模式
        trajectory_enabled_in_config = config.get('trajectory_settings', {}).get('enabled', False)
        self.simulation_mode = "trajectory" if trajectory_enabled_in_config else "single_point"
        self.large_terrain_size_km = 10  # 地形尺寸（公里）
        self.large_terrain_resolution_m = 2  # 分辨率（米
        # --- ✅ Part B: YOLO 数据（改为多文件支持）---
        yolo_settings = config.get('yolo_input_settings', {})
        self.available_yolo_files = []
        
        # ✅ 改为列表，支持多个文件
        default_file = yolo_settings.get('image_filename', '')
        self.selected_yolo_files = [default_file] if default_file else []
        
        self.max_detections = yolo_settings.get('max_detections', 50)
        self.random_sample = False

        # --- 单点模拟参数 ---
        sim_settings = config.get('simulation_settings', {})
        self.camera_position = sim_settings.get('camera_position_local', [302500, 3997500, 2500.0])
        self.camera_attitude = sim_settings.get('camera_attitude_deg', {'roll': 0.0, 'pitch': -30.0, 'yaw': 45.0})

        # --- 航线模拟参数 ---
        traj_settings = config.get('trajectory_settings', {})
        self.trajectory_path = traj_settings.get('path_world', [])
        self.flight_altitude_agl = traj_settings.get('flight_altitude_agl', 1200.0)
        self.photo_interval_meters = traj_settings.get('photo_interval_meters', 500.0)
        self.trajectory_attitude = traj_settings.get('camera_attitude_deg', {
            "roll": 0.0, "pitch": 0.0, "yaw": "auto"
        })
        
        # --- 通用参数 ---
        # 相机内参
        camera_params = self._load_camera_params(self.camera_config_path)
        if camera_params and 'camera_intrinsics' in camera_params:
            intrinsics = camera_params['camera_intrinsics']
            self.focal_length_px = intrinsics.get('focal_length_px', 4000.0)
            self.sensor_size_px = intrinsics.get('sensor_size_px', [4000, 3000])
        else:
            print("⚠️ Warning: Could not load camera intrinsics, using defaults.")
            self.focal_length_px = 4000.0
            self.sensor_size_px = [4000, 3000]

        # 参考高程
        self.ref_elevation_mode = sim_settings.get('reference_elevation_mode', 'camera_nadir')
        self.custom_ref_elevation = sim_settings.get('custom_reference_elevation', 900.0)

        # 视图控制
        self.show_camera_coverage = True
        self.show_ref_plane_in_3d = True
        
        # 绘制状态
        self.is_drawing_trajectory = False

        # --- 回调机制 ---
        self._update_callbacks = []
        
        print(f"StateManager: Initialized. Mode='{self.simulation_mode}', YOLO files={len(self.selected_yolo_files)}")

    def set_ready(self, is_ready=True):
        """✅ 新增: 设置状态管理器为就绪状态"""
        print(f"StateManager: Ready status set to {is_ready}.")
        self._is_ready = is_ready

    def _load_camera_params(self, camera_config_path):
        """加载相机参数配置文件"""
        if not camera_config_path:
            return None
        
        if not os.path.isabs(camera_config_path):
            camera_config_path = os.path.join(os.getcwd(), camera_config_path)
        
        if not os.path.exists(camera_config_path):
            return None
        
        try:
            with open(camera_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
            
    def register_update_callback(self, callback):
        """注册状态更新回调"""
        self._update_callbacks.append(callback)

    # gui/state_manager.py -> update_state method (精准触发版)

    # gui/state_manager.py -> update_state method

    def update_state(self, **kwargs):
        """
        更新状态属性。
        注意：此方法只更新状态，不会自动触发任何计算。
        计算只能通过用户点击"运行模拟"按钮来手动触发。
        """
        # ✅ 移除 suppress_callbacks 参数（不再需要）
        
        updated_keys = []
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                updated_keys.append(key)
            else:
                print(f"⚠️ Warning: Attempted to update non-existent state key '{key}'")
        
        if updated_keys:
            print(f"StateManager: State updated -> {updated_keys} (no auto-recalc)")




