# core/report_generator.py (Phase 1.4 最终修复版)

import numpy as np
import pandas as pd

class ReportGenerator:
    """
    根据模拟结果生成统计数据和报告。
    """
    def __init__(self, results):
        """
        初始化报告生成器。
        
        Args:
            results (list): georeferencing_engine 返回的结果字典列表。
        """
        self.results = results
        # ✅ 修复: 即使结果为空，也能安全地计算统计数据
        self.stats = self._calculate_statistics()

    def _calculate_statistics(self):
        """计算核心统计指标。"""
        # ✅ 修复: 如果结果为空，返回一个包含默认值的字典
        if not self.results:
            return {
                'count': 0,
                'rmse': 0.0,
                'mean': 0.0,
                'max': 0.0,
                'min': 0.0,
                'std': 0.0
            }

        errors = [res['error_m'] for res in self.results]
        
        stats_dict = {
            'count': len(errors),
            'rmse': np.sqrt(np.mean(np.square(errors))),
            'mean': np.mean(errors),
            'max': np.max(errors),
            'min': np.min(errors),
            'std': np.std(errors)
        }
        return stats_dict

    def generate_dataframe(self):
        """将结果转换为Pandas DataFrame。"""
        if not self.results:
            return pd.DataFrame() # 返回一个空的DataFrame

        data_for_df = []
        for i, res in enumerate(self.results):
            row = {
                'point_index': i,
                'pixel_x': res['pixel'][0],
                'pixel_y': res['pixel'][1],
                'true_x': res['slope_projection'][0],
                'true_y': res['slope_projection'][1],
                'true_z': res['slope_projection'][2],
                'planar_x': res['planar_projection'][0],
                'planar_y': res['planar_projection'][1],
                'planar_z': res['planar_projection'][2],
                'error_2d_m': res['error_m'],
                'camera_x': res['camera_pos'][0],
                'camera_y': res['camera_pos'][1],
                'camera_z': res['camera_pos'][2],
                'waypoint_index': res.get('waypoint_index', 0)
            }
            data_for_df.append(row)
        
        df = pd.DataFrame(data_for_df)
        return df

    def generate_csv(self, output_path):
        """将结果保存为CSV文件。"""
        df = self.generate_dataframe()
        if not df.empty:
            df.to_csv(output_path, index=False, float_format='%.3f')
            print(f"✅ Report successfully saved to '{output_path}'")
        else:
            print("⚠️ No data to save, CSV file not created.")
