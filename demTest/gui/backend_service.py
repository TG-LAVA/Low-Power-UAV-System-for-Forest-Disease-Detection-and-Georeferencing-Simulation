# core/backend_service.py (Part B 完整版 - 性能优化 + 多文件批量处理)

import numpy as np
import random

from core.data_loader import DataLoader
from core.camera_model import CameraModel
from core.georeferencing_engine import GeoreferencingEngine
from core.report_generator import ReportGenerator
from core.dem_generator import create_slope_dem
import os
class BackendService:
    def __init__(self, initial_state):
        print("--- [Backend Service] Initializing (Optimized Mode + Multi-File Support) ---")
        self.base_camera_params = DataLoader.load_camera_params(initial_state.camera_config_path)
        if self.base_camera_params is None:
            raise RuntimeError("BackendService failed to initialize: Camera parameters could not be loaded.")
        
        self.dem_data = None
        self.dem_transform = None
        self.geo_engine = None
        print("✅ [Backend Service] Ready (high-performance + multi-file batch processing enabled).")

    def _prepare_scene(self, state):
        """根据当前场景状态，加载DEM，并初始化地理引擎。"""
        print(f"   - Preparing scene: '{state.current_scene}'")
        
        if state.current_scene == "virtual_slope":
            self.dem_data, self.dem_transform = create_slope_dem(
                slope_deg=state.virtual_slope_angle
            )
        elif state.current_scene == "large_terrain":
            self.dem_data, self.dem_transform = DataLoader.load_dem(state.dem_path_large)
        else:
            self.dem_data, self.dem_transform = DataLoader.load_dem(state.dem_path_complex)
        
        self.geo_engine = GeoreferencingEngine(self.dem_data, self.dem_transform)
        return True

    def run_simulation_for_state(self, state):
        print(f"\n🚀 [Backend Service] Executing new run for state (Mode: {state.simulation_mode})...")

        if not self._prepare_scene(state):
            return self._get_empty_results()

        cameras_to_process = self._prepare_cameras(state)
        if not cameras_to_process:
            return self._get_empty_results()

        # ✅ 核心逻辑改造: 根据关联模式处理YOLO数据
        yolo_files = state.selected_yolo_files
        if not yolo_files:
            print("   - Warning: No YOLO files selected. Simulation will have no targets.")
            return self._get_empty_results()

        all_results = []
        
        # --- 固定模式 (Fixed Mode) ---
        if state.simulation_mode == 'single_point' or state.yolo_association_mode == 'fixed':
            print(f"   - YOLO Mode: Fixed. Using '{yolo_files[0]}' for all cameras.")
            # 只使用列表中的第一个文件
            pixels_to_process = self._select_yolo_pixels(state, yolo_files[0])
            if not pixels_to_process:
                return self._get_empty_results()

            for i, cam_info in enumerate(cameras_to_process):
                # (这里的内部投影逻辑与之前版本相同)
                results_for_cam = self._process_camera(cam_info, pixels_to_process, state)
                # 为结果添加源文件信息
                for res in results_for_cam:
                    res['source_file'] = os.path.basename(yolo_files[0])
                all_results.extend(results_for_cam)

        # --- 循环模式 (Cycle Mode) ---
        elif state.yolo_association_mode == 'cycle':
            print(f"   - YOLO Mode: Cycle. Cycling through {len(yolo_files)} file(s).")
            num_yolo_files = len(yolo_files)
            
            for i, cam_info in enumerate(cameras_to_process):
                # 使用取模运算实现循环
                yolo_file_for_this_cam = yolo_files[i % num_yolo_files]
                print(f"     - Waypoint {i}: Using '{yolo_file_for_this_cam}'")
                
                pixels_to_process = self._select_yolo_pixels(state, yolo_file_for_this_cam)
                if not pixels_to_process:
                    continue # 如果某个文件加载失败，跳过这个航点

                results_for_cam = self._process_camera(cam_info, pixels_to_process, state)
                # 为结果添加源文件信息
                for res in results_for_cam:
                    res['source_file'] = os.path.basename(yolo_file_for_this_cam)
                all_results.extend(results_for_cam)

        # --- 结果汇总 ---
        if not all_results:
            print("\n❌ [Backend Service] Run finished with no valid projection results.")
            report_gen = ReportGenerator([])
        else:
            report_gen = ReportGenerator(all_results)
        
        stats = report_gen.stats
        print(f"✅ [Backend Service] Run finished. Final RMSE: {stats['rmse']:.3f} m")
        
        return {
            'results': all_results, 
            'stats': stats,
            'dem_data': self.dem_data,
            'dem_transform': self.dem_transform
        }
    
    def _process_camera(self, cam_info, pixels, state):
        """辅助方法：处理单个相机和其对应的像素点列表"""
        camera = cam_info['camera']
        reference_elevation = self._calculate_reference_elevation(camera, state)
        waypoint_index = cam_info.get('waypoint_index', 0)
        
        results = []
        for px_tuple in pixels:
            px = tuple(px_tuple)
            true_point_data = self.geo_engine.georeference_point(px, camera)
            if not true_point_data['success']: continue

            true_point = np.array([true_point_data['world_x'], true_point_data['world_y'], true_point_data['world_z']])
            ray_origin, ray_dir = camera.pixel_to_ray(px)
            if abs(ray_dir[2]) < 1e-9: continue
            
            t = (reference_elevation - ray_origin[2]) / ray_dir[2]
            if t < 0: continue
            false_point = ray_origin + t * ray_dir
            error_distance = np.linalg.norm(true_point[:2] - false_point[:2])

            results.append({
                "pixel": px, "slope_projection": true_point, "planar_projection": false_point,
                "error_m": error_distance, "camera_pos": camera.camera_pos_world,
                "waypoint_index": waypoint_index
            })
        return results
    def _process_pixels_batch(self, camera, pixels_list, reference_elevation, waypoint_index, source_file=None):
        """
        ✅ 批量处理一个相机的所有像素点（优化版 + 文件来源标记）
        
        Args:
            camera: 相机模型
            pixels_list: 像素点列表
            reference_elevation: 参考高程
            waypoint_index: 航点索引
            source_file: 数据来源文件名（Part B新增）
        """
        results = []
        
        # 第1阶段：批量地理配准
        true_points_3d = []
        valid_pixels = []
        
        for px in pixels_list:
            px_tuple = tuple(px)
            true_point_data = self.geo_engine.georeference_point(px_tuple, camera)
            
            if true_point_data['success']:
                true_point = np.array([
                    true_point_data['world_x'],
                    true_point_data['world_y'],
                    true_point_data['world_z']
                ])
                true_points_3d.append(true_point)
                valid_pixels.append(px_tuple)
        
        if len(true_points_3d) == 0:
            return []
        
        # 转换为NumPy数组以便批量处理
        true_points_3d = np.array(true_points_3d)  # shape: (N, 3)
        
        # 第2阶段：批量计算平面投影点
        false_points_3d = []
        
        for i, px in enumerate(valid_pixels):
            ray_origin, ray_dir = camera.pixel_to_ray(px)
            
            if abs(ray_dir[2]) < 1e-9:
                false_points_3d.append(None)
                continue
            
            # 计算射线与参考平面的交点
            t = (reference_elevation - ray_origin[2]) / ray_dir[2]
            
            if t < 0:
                false_points_3d.append(None)
                continue
            
            false_point = ray_origin + t * ray_dir
            false_points_3d.append(false_point)
        
        # 第3阶段：批量计算误差
        for i in range(len(valid_pixels)):
            if false_points_3d[i] is None:
                continue
            
            true_point = true_points_3d[i]
            false_point = false_points_3d[i]
            
            # 计算水平误差（只考虑XY平面）
            error_distance = np.linalg.norm(true_point[:2] - false_point[:2])
            
            result_item = {
                "pixel": valid_pixels[i],
                "slope_projection": true_point.tolist(),
                "planar_projection": false_point.tolist(),
                "error_m": float(error_distance),
                "camera_pos": camera.camera_pos_world.tolist(),
                "waypoint_index": waypoint_index
            }
            
            # ✅ Part B: 添加数据来源标记
            if source_file:
                result_item["source_file"] = source_file
            
            results.append(result_item)
        
        return results

    def _select_yolo_pixels_from_file(self, state, yolo_file):
        """
        ✅ Part B: 从指定的YOLO文件加载检测数据
        
        Args:
            state: 状态管理器
            yolo_file: YOLO文件名
            
        Returns:
            像素点列表
        """
        detections_np = DataLoader.load_yolo_detections(state.yolo_dataset_dir, yolo_file)
        if detections_np is None: 
            return []
        
        full_detections = detections_np.tolist()
        if not full_detections: 
            return []
        
        num_to_select = min(state.max_detections, len(full_detections))
        
        if state.random_sample:
            return random.sample(full_detections, num_to_select)
        else:
            return full_detections[:num_to_select]

    def _select_yolo_pixels(self, state, selected_yolo_file):
        # ✅ 修改: 接收单个文件名作为参数
        detections_np = DataLoader.load_yolo_detections(state.yolo_dataset_dir, selected_yolo_file)
        if detections_np is None: return []
        full_detections = detections_np.tolist()
        if not full_detections: return []
        num_to_select = min(state.max_detections, len(full_detections))
        if state.random_sample:
            return random.sample(full_detections, num_to_select)
        else:
            return full_detections[:num_to_select]

    def _prepare_cameras(self, state):
        """
        准备相机列表（支持单点和航线模式）
        ✅ 性能优化版：批量查询地面高程
        """
        cameras = []
        
        if state.simulation_mode == 'trajectory':
            path_points = state.trajectory_path
            altitude_agl = state.flight_altitude_agl
            interval = state.photo_interval_meters
            attitude = state.trajectory_attitude

            if not path_points or len(path_points) < 2:
                print("   - Warning: Trajectory path requires at least two points.")
                return []

            # 构建航线段
            total_path_length = 0.0
            segments = []
            
            for i in range(len(path_points) - 1):
                start_node = np.array([path_points[i]['x'], path_points[i]['y']])
                end_node = np.array([path_points[i+1]['x'], path_points[i+1]['y']])
                segment_vec = end_node - start_node
                segment_len = np.linalg.norm(segment_vec)
                
                if segment_len < 1e-6: 
                    continue
                
                segments.append({
                    'start_node': start_node,
                    'dir_vec': segment_vec / segment_len,
                    'len': segment_len,
                    'start_dist': total_path_length,
                    'segment_index': i
                })
                total_path_length += segment_len
            
            if total_path_length < interval:
                num_photos = 1
            else:
                num_photos = int(total_path_length / interval) + 1

            # ✅ 批量查询地面高程（性能优化关键点）
            camera_positions_2d = []
            camera_infos = []
            
            current_segment_idx = 0
            
            for i in range(num_photos):
                dist_along_path = i * interval
                
                if dist_along_path > total_path_length:
                    dist_along_path = total_path_length
                
                # 找到当前距离所在的航段
                found_segment = False
                for j in range(current_segment_idx, len(segments)):
                    seg = segments[j]
                    if seg['start_dist'] <= dist_along_path <= seg['start_dist'] + seg['len'] + 1e-9:
                        current_segment = seg
                        current_segment_idx = j
                        found_segment = True
                        break
                
                if not found_segment:
                    if abs(dist_along_path - total_path_length) < 1e-9:
                        current_segment = segments[-1]
                        dist_into_segment = current_segment['len']
                    else: 
                        continue
                else:
                    dist_into_segment = dist_along_path - current_segment['start_dist']

                current_pos_2d = current_segment['start_node'] + current_segment['dir_vec'] * dist_into_segment
                
                camera_positions_2d.append(current_pos_2d)
                camera_infos.append({
                    'segment': current_segment,
                    'segment_index': current_segment['segment_index']
                })
            
            # ✅ 批量查询所有相机位置的地面高程（减少DEM访问次数）
            if len(camera_positions_2d) > 0:
                camera_positions_2d_array = np.array(camera_positions_2d)
                ground_elevations = self.geo_engine.get_elevation_batch(camera_positions_2d_array)
                
                # 构建相机对象
                for i, (pos_2d, ground_z, cam_info) in enumerate(zip(camera_positions_2d, ground_elevations, camera_infos)):
                    if np.isnan(ground_z):
                        print(f"   - Warning: Camera {i} at ({pos_2d[0]:.1f}, {pos_2d[1]:.1f}) has invalid ground elevation, skipping.")
                        continue
                    
                    camera_z = ground_z + altitude_agl
                    position = np.array([pos_2d[0], pos_2d[1], camera_z])
                    
                    # 计算姿态（处理自动偏航）
                    current_attitude = attitude.copy()
                    if isinstance(current_attitude.get('yaw'), str) and current_attitude['yaw'].lower() == 'auto':
                        direction_vector = cam_info['segment']['dir_vec']
                        yaw_angle_rad = np.arctan2(direction_vector[0], direction_vector[1])
                        current_attitude['yaw'] = np.rad2deg(yaw_angle_rad)
                    
                    cam_params = self._build_camera_params(position, current_attitude)
                    cameras.append({
                        'camera': CameraModel(cam_params), 
                        'waypoint_index': cam_info['segment_index']
                    })
        
        else:  # 单点模式
            position = state.camera_position
            attitude = state.camera_attitude
            cam_params = self._build_camera_params(position, attitude)
            cameras.append({'camera': CameraModel(cam_params), 'waypoint_index': 0})
        
        print(f"   - Prepared {len(cameras)} camera(s) for simulation (optimized).")
        return cameras

    def _build_camera_params(self, position, attitude):
        """构建相机参数字典"""
        cam_params = self.base_camera_params.copy()
        cam_params['camera_extrinsics'] = {
            "position_meters": list(position),
            "rotation_degrees": attitude
        }
        return cam_params

    def _calculate_reference_elevation(self, camera, state):
        """计算参考高程"""
        if state.ref_elevation_mode == "camera_nadir":
            intersection = self.geo_engine.intersect_ray_with_dem(
                camera.camera_pos_world, 
                np.array([0, 0, -1.0])
            )
            return intersection[2] if intersection is not None else 0.0
        return state.custom_ref_elevation

    def _get_empty_results(self):
        """返回空结果集"""
        return {
            'results': [], 
            'stats': {'rmse': 0, 'mean': 0, 'max': 0, 'min': 0, 'count': 0},
            'file_stats': {},  # ✅ Part B: 每个文件的统计
            'dem_data': self.dem_data,
            'dem_transform': self.dem_transform
        }
