# gui/widgets/control_panel.py (Part C - 完整优化版：美化UI + 导出功能)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QPushButton, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QListWidget, QListWidgetItem, QScrollArea, QFrame,QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
import json
import csv
from datetime import datetime
import os
class ControlPanel(QWidget):
    run_simulation_requested = pyqtSignal()
    draw_trajectory_requested = pyqtSignal()
    export_requested = pyqtSignal(str)  # ✅ 新增：导出信号（格式：csv/json/excel）
    scene_changed_requested = pyqtSignal()
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.current_results = None  # ✅ 存储最新的模拟结果
        self._init_ui()
        self.update_controls_from_state()
    def _init_ui(self):
        # ✅ 使用滚动区域包裹整个控制面板
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # 创建主容器
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        
        # === 标题区域 ===
        title_label = QLabel("📐 Simulation Control Panel")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        layout.addWidget(title_label)
        
        # === 1. 场景选择 ===
        layout.addWidget(self._create_scene_group())
        
        # === 2. 模拟模式 ===
        layout.addWidget(self._create_mode_group())
        
        # === 3. YOLO数据选择 ===
        layout.addWidget(self._create_yolo_group())
        layout.addWidget(self._create_camera_params_group())
        # === 4. 参考高程设置 ===
        layout.addWidget(self._create_reference_group())
        
        # === 5. 可视化选项 ===
        layout.addWidget(self._create_visualization_group())
        
        # === 6. 操作按钮区 ===
        layout.addWidget(self._create_action_buttons())
        
        # === 7. 导出功能区 ===
        layout.addWidget(self._create_export_group())
        
        layout.addStretch()
        
        # 设置滚动区域
        scroll.setWidget(container)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _create_camera_params_group(self):
        group = QGroupBox("Camera Intrinsics")
        layout = QFormLayout()

        self.focal_length_spin = QDoubleSpinBox()
        self.focal_length_spin.setRange(100, 20000)
        self.focal_length_spin.setValue(self.state.focal_length_px)
        self.focal_length_spin.setSuffix(" px")
        self.focal_length_spin.valueChanged.connect(
            lambda val: self.state.update_state(focal_length_px=val)
        )
        layout.addRow("Focal Length:", self.focal_length_spin)

        sensor_layout = QHBoxLayout()
        self.sensor_w_spin = QSpinBox()
        self.sensor_w_spin.setRange(100, 20000)
        self.sensor_w_spin.setValue(self.state.sensor_size_px[0])
        self.sensor_h_spin = QSpinBox()
        self.sensor_h_spin.setRange(100, 20000)
        self.sensor_h_spin.setValue(self.state.sensor_size_px[1])
        sensor_layout.addWidget(QLabel("W:"))
        sensor_layout.addWidget(self.sensor_w_spin)
        sensor_layout.addWidget(QLabel("H:"))
        sensor_layout.addWidget(self.sensor_h_spin)
        # 连接信号
        self.sensor_w_spin.valueChanged.connect(self._update_sensor_size)
        self.sensor_h_spin.valueChanged.connect(self._update_sensor_size)
        layout.addRow("Sensor Size:", sensor_layout)

        group.setLayout(layout)
        return group
    
    def _create_scene_group(self):
        group = QGroupBox("Scene Selection")
        layout = QVBoxLayout()
        
        self.scene_combo = QComboBox()
        self.scene_combo.addItems([
            "complex_terrain", 
            "virtual_slope",
            "🌍 large_terrain"  # ✅ 新增
        ])
        
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        
        layout.addWidget(QLabel("Scene Type:"))
        layout.addWidget(self.scene_combo)
        
        # === 虚拟坡度控件 ===
        self.virtual_slope_widget = QWidget()
        slope_layout = QHBoxLayout(self.virtual_slope_widget)
        slope_layout.setContentsMargins(0, 5, 0, 0)
        slope_layout.addWidget(QLabel("Slope Angle:"))
        self.slope_spin = QDoubleSpinBox()
        self.slope_spin.setRange(0, 89)
        self.slope_spin.setValue(15)
        self.slope_spin.setSuffix(" °")
        self.slope_spin.valueChanged.connect(
            lambda val: self.state.update_state(virtual_slope_angle=val)
        )
        slope_layout.addWidget(self.slope_spin)
        layout.addWidget(self.virtual_slope_widget)
        
        # ✅ 新增: 超大地形控件
        self.large_terrain_widget = QWidget()
        large_layout = QVBoxLayout(self.large_terrain_widget)
        large_layout.setContentsMargins(0, 5, 0, 0)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.terrain_size_spin = QSpinBox()
        self.terrain_size_spin.setRange(5, 50)
        self.terrain_size_spin.setValue(20)
        self.terrain_size_spin.setSuffix(" km")
        self.terrain_size_spin.valueChanged.connect(
            lambda val: self.state.update_state(large_terrain_size_km=val)
        )
        size_layout.addWidget(self.terrain_size_spin)
        large_layout.addLayout(size_layout)
        
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))
        self.terrain_res_spin = QSpinBox()
        self.terrain_res_spin.setRange(1, 10)
        self.terrain_res_spin.setValue(2)
        self.terrain_res_spin.setSuffix(" m/px")
        self.terrain_res_spin.valueChanged.connect(
            lambda val: self.state.update_state(large_terrain_resolution_m=val)
        )
        res_layout.addWidget(self.terrain_res_spin)
        large_layout.addLayout(res_layout)
        
        # 性能提示
        perf_label = QLabel("⚠️ Generation may take 10-30s")
        perf_label.setStyleSheet("color: #e67e22; font-size: 9pt;")
        perf_label.setWordWrap(True)
        large_layout.addWidget(perf_label)
        
        layout.addWidget(self.large_terrain_widget)
        self.large_terrain_widget.setVisible(False)  # 默认隐藏
        
        group.setLayout(layout)
        return group
        
    # gui/app_window.py -> _on_scene_changed method

    # gui/widgets/control_panel.py

    def _on_scene_changed(self, index):
        """处理场景切换"""
        scene_text = self.scene_combo.itemText(index)
        
        # 确定场景类型并显示对应控件
        if "virtual_slope" in scene_text:
            scene_key = "virtual_slope"
            self.virtual_slope_widget.setVisible(True)
            self.large_terrain_widget.setVisible(False)
        elif "large_terrain" in scene_text:
            scene_key = "large_terrain"
            self.virtual_slope_widget.setVisible(False)
            self.large_terrain_widget.setVisible(True)
        else:
            scene_key = "complex_terrain"
            self.virtual_slope_widget.setVisible(False)
            self.large_terrain_widget.setVisible(False)
        
        # 更新状态
        self.state.update_state(current_scene=scene_key)
        
        # 通知 AppWindow 重新加载地形
        self.scene_changed_requested.emit()



    def _create_mode_group(self):
        """创建模拟模式组"""
        group = QGroupBox("Simulation Mode")
        layout = QVBoxLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["single_point", "trajectory"])
        
        # ✅ 核心修复：改用 currentIndexChanged 信号（发送整数索引）
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        
        layout.addWidget(QLabel("Mode:"))
        layout.addWidget(self.mode_combo)
        
        # 单点模式
        self.single_point_widget = self._create_single_point_widget()
        layout.addWidget(self.single_point_widget)
        
        # 航线模式
        self.trajectory_widget = self._create_trajectory_widget()
        self.trajectory_widget.setVisible(False)
        layout.addWidget(self.trajectory_widget)
        
        group.setLayout(layout)
        return group
    
    def _create_single_point_widget(self):
        """创建单点模式控件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 位置
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position(X,Y,Z):"))
        self.pos_x = QDoubleSpinBox()
        self.pos_x.setRange(-1e9, 1e9)
        self.pos_x.setValue(500000)
        self.pos_y = QDoubleSpinBox()
        self.pos_y.setRange(-1e9, 1e9)
        self.pos_y.setValue(4500000)
        self.pos_z = QDoubleSpinBox()
        self.pos_z.setRange(0, 10000)
        self.pos_z.setValue(150)
        pos_layout.addWidget(self.pos_x)
        pos_layout.addWidget(self.pos_y)
        pos_layout.addWidget(self.pos_z)
        layout.addLayout(pos_layout)
        
        # 姿态
        att_layout = QHBoxLayout()
        att_layout.addWidget(QLabel("Attitude (R,P,Y):"))
        self.roll = QDoubleSpinBox()
        self.roll.setRange(-180, 180)
        self.roll.setValue(0)
        self.roll.setSuffix("°")
        self.pitch = QDoubleSpinBox()
        self.pitch.setRange(-90, 90)
        self.pitch.setValue(-30)
        self.pitch.setSuffix("°")
        self.yaw = QDoubleSpinBox()
        self.yaw.setRange(-180, 180)
        self.yaw.setValue(45)
        self.yaw.setSuffix("°")
        att_layout.addWidget(self.roll)
        att_layout.addWidget(self.pitch)
        att_layout.addWidget(self.yaw)
        layout.addLayout(att_layout)
        
        return widget
    
    # gui/widgets/control_panel.py -> _create_trajectory_widget method

    def _create_trajectory_widget(self):
        """创建航线模式控件（增强版：添加相机姿态控制）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 绘制按钮
        self.draw_traj_btn = QPushButton("🖊️ Draw Trajectory on Map")
        self.draw_traj_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.draw_traj_btn.clicked.connect(self.draw_trajectory_requested.emit)
        layout.addWidget(self.draw_traj_btn)
        
        # 坐标显示（紧凑版）
        coord_widget = QWidget()
        coord_layout = QVBoxLayout(coord_widget)
        coord_layout.setContentsMargins(0, 5, 0, 0)
        coord_layout.setSpacing(3)
        
        # 起点
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start:"))
        self.start_x = QDoubleSpinBox()
        self.start_x.setRange(-1e9, 1e9)
        self.start_x.setReadOnly(True)
        self.start_x.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.start_y = QDoubleSpinBox()
        self.start_y.setRange(-1e9, 1e9)
        self.start_y.setReadOnly(True)
        self.start_y.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        start_layout.addWidget(self.start_x)
        start_layout.addWidget(self.start_y)
        coord_layout.addLayout(start_layout)
        
        # 终点
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End:"))
        self.end_x = QDoubleSpinBox()
        self.end_x.setRange(-1e9, 1e9)
        self.end_x.setReadOnly(True)
        self.end_x.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.end_y = QDoubleSpinBox()
        self.end_y.setRange(-1e9, 1e9)
        self.end_y.setReadOnly(True)
        self.end_y.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        end_layout.addWidget(self.end_x)
        end_layout.addWidget(self.end_y)
        coord_layout.addLayout(end_layout)
        
        layout.addWidget(coord_widget)
        
        # 飞行参数
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Altitude:"))
        self.altitude = QDoubleSpinBox()
        self.altitude.setRange(10, 10000)
        self.altitude.setValue(1200)
        self.altitude.setSuffix(" m")
        self.altitude.valueChanged.connect(
            lambda val: self.state.update_state(flight_altitude_agl=val)
        )
        param_layout.addWidget(self.altitude)
        
        param_layout.addWidget(QLabel("Interval:"))
        self.interval = QDoubleSpinBox()
        self.interval.setRange(1, 10000)
        self.interval.setValue(500)
        self.interval.setSuffix(" m")
        self.interval.valueChanged.connect(
            lambda val: self.state.update_state(photo_interval_meters=val)
        )
        param_layout.addWidget(self.interval)
        layout.addLayout(param_layout)
        
        # ✅ 新增：航线模式的相机姿态控制
        attitude_layout = QVBoxLayout()
        attitude_layout.addWidget(QLabel("Camera Attitude:"))
        
        att_controls = QHBoxLayout()
        att_controls.addWidget(QLabel("R:"))
        self.traj_roll = QDoubleSpinBox()
        self.traj_roll.setRange(-180, 180)
        self.traj_roll.setValue(0)
        self.traj_roll.setSuffix("°")
        self.traj_roll.valueChanged.connect(self._update_trajectory_attitude)
        att_controls.addWidget(self.traj_roll)
        
        att_controls.addWidget(QLabel("P:"))
        self.traj_pitch = QDoubleSpinBox()
        self.traj_pitch.setRange(-90, 90)
        self.traj_pitch.setValue(-30)
        self.traj_pitch.setSuffix("°")
        self.traj_pitch.valueChanged.connect(self._update_trajectory_attitude)
        att_controls.addWidget(self.traj_pitch)
        
        att_controls.addWidget(QLabel("Y:"))
        self.traj_yaw = QDoubleSpinBox()
        self.traj_yaw.setRange(-180, 180)
        self.traj_yaw.setValue(0)
        self.traj_yaw.setSuffix("°")
        self.traj_yaw.setEnabled(False)  # 默认禁用，因为通常使用自动偏航
        self.traj_yaw.valueChanged.connect(self._update_trajectory_attitude)
        att_controls.addWidget(self.traj_yaw)
        
        attitude_layout.addLayout(att_controls)
        
        # 自动偏航选项
        self.auto_yaw_check = QCheckBox("Auto Yaw")
        self.auto_yaw_check.setChecked(True)
        self.auto_yaw_check.stateChanged.connect(self._on_auto_yaw_changed)
        attitude_layout.addWidget(self.auto_yaw_check)
        
        layout.addLayout(attitude_layout)
        
        return widget

    def _update_trajectory_attitude(self):
        """✅ 新增：更新航线模式的相机姿态"""
        yaw_value = "auto" if self.auto_yaw_check.isChecked() else self.traj_yaw.value()
        
        self.state.update_state(
            trajectory_attitude={
                'roll': self.traj_roll.value(),
                'pitch': self.traj_pitch.value(),
                'yaw': yaw_value
            }
        )

    def _on_auto_yaw_changed(self, state):
        """✅ 新增：自动偏航开关切换"""
        is_auto = bool(state)
        self.traj_yaw.setEnabled(not is_auto)
        self._update_trajectory_attitude()

    
    def _create_yolo_group(self):
        # ✅ 修改: 添加YOLO关联模式
        group = QGroupBox("YOLO Detection Data")
        layout = QVBoxLayout()
        
        # 文件选择按钮 (与您提供的版本相同)
        btn_layout = QHBoxLayout()
        self.select_files_btn = QPushButton("📁  Select Files (Multi-select)")
        self.select_files_btn.clicked.connect(self._select_yolo_files)
        self.clear_files_btn = QPushButton("🗑️")
        self.clear_files_btn.setFixedWidth(40)
        self.clear_files_btn.clicked.connect(self._clear_yolo_files)
        btn_layout.addWidget(self.select_files_btn)
        btn_layout.addWidget(self.clear_files_btn)
        layout.addLayout(btn_layout)
        
        self.yolo_file_list = QListWidget()
        self.yolo_file_list.setMaximumHeight(100)
        layout.addWidget(self.yolo_file_list)
        
        # ✅ 新增: 关联模式
        assoc_layout = QHBoxLayout()
        assoc_layout.addWidget(QLabel("Association Mode:"))
        self.yolo_assoc_combo = QComboBox()
        self.yolo_assoc_combo.addItems(["Fixed", "Cycle"])
        self.yolo_assoc_combo.currentIndexChanged.connect(self._on_yolo_assoc_changed)
        assoc_layout.addWidget(self.yolo_assoc_combo)
        layout.addLayout(assoc_layout)

        # 采样设置 (与您提供的版本相同)
        sample_layout = QHBoxLayout()
        self.random_sample_check = QCheckBox("Random Sample")
        self.random_sample_check.stateChanged.connect(
            lambda state: self.state.update_state(random_sample=bool(state))
        )
        sample_layout.addWidget(self.random_sample_check)
        sample_layout.addWidget(QLabel("per file:"))
        self.max_detections = QSpinBox()
        self.max_detections.setRange(1, 10000)
        self.max_detections.setValue(50)
        self.max_detections.valueChanged.connect(
            lambda val: self.state.update_state(max_detections=val)
        )
        sample_layout.addWidget(self.max_detections)
        layout.addLayout(sample_layout)
        
        group.setLayout(layout)
        return group
    
    
    def _create_reference_group(self):
        """✅ 修复版：创建参考高程组，并关联UI状态"""
        group = QGroupBox("Reference Elevation")
        layout = QVBoxLayout()
        
        self.ref_mode_combo = QComboBox()
        self.ref_mode_combo.addItems(["camera_nadir", "custom_value"])
        
        # ✅ 关键修复 3：连接信号以控制UI
        self.ref_mode_combo.currentTextChanged.connect(self._on_ref_mode_changed)
        
        layout.addWidget(self.ref_mode_combo)
        
        # 将自定义输入框和标签放入一个QWidget中以便整体控制
        self.custom_ref_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_ref_widget)
        custom_layout.setContentsMargins(0, 5, 0, 0)
        
        custom_layout.addWidget(QLabel("Custom Value:"))
        self.custom_ref = QDoubleSpinBox()
        self.custom_ref.setRange(-1000, 10000)
        self.custom_ref.setValue(0)
        self.custom_ref.setSuffix(" m")
        self.custom_ref.valueChanged.connect(
            lambda val: self.state.update_state(custom_ref_elevation=val, trigger_recalc=False)
        )
        custom_layout.addWidget(self.custom_ref)
        layout.addWidget(self.custom_ref_widget)
        
        group.setLayout(layout)
        return group
    
    def _on_ref_mode_changed(self, text):
        """✅ 新增：当参考高程模式改变时，更新状态并控制UI"""
        mode_key = "custom_value" if "custom_value" in text else "camera_nadir"
        is_custom = (mode_key == "custom_value")
        
        # 控制自定义输入框的可用性
        self.custom_ref_widget.setEnabled(is_custom)
        
        # 更新状态
        self.state.update_state(ref_elevation_mode=mode_key, trigger_recalc=False)

    def _create_visualization_group(self):
        """✅ 修复版：创建可视化选项组（仅更新状态，不触发重绘）"""
        group = QGroupBox("Visualization Options")
        layout = QVBoxLayout()
        
        # --- 相机覆盖范围 ---
        self.show_coverage_check = QCheckBox("Show Camera Coverage")
        
        # ✅ 从state初始化
        self.show_coverage_check.setChecked(self.state.show_camera_coverage)
        
        # ✅ 关键修复：信号只连接到状态更新，不连接到重绘
        self.show_coverage_check.stateChanged.connect(
            lambda state: self.state.update_state(show_camera_coverage=bool(state), trigger_recalc=False)
        )
        
        layout.addWidget(self.show_coverage_check)
        
        # --- 3D参考平面 ---
        self.show_ref_plane_check = QCheckBox("Show Reference Plane in 3D View")
        
        # ✅ 从state初始化
        self.show_ref_plane_check.setChecked(self.state.show_ref_plane_in_3d)
        
        # ✅ 关键修复：信号只连接到状态更新，不连接到重绘
        self.show_ref_plane_check.stateChanged.connect(
            lambda state: self.state.update_state(show_ref_plane_in_3d=bool(state), trigger_recalc=False)
        )
        
        layout.addWidget(self.show_ref_plane_check)
        
        group.setLayout(layout)
        return group
        

    def _create_action_buttons(self):
        """创建操作按钮"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 5)
        # 运行模拟按钮
        self.run_sim_button = QPushButton("🚀 Run Simulation")
        self.run_sim_button.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.run_sim_button.clicked.connect(self.run_simulation_requested.emit)
        layout.addWidget(self.run_sim_button)
        
        return widget
    
    # gui/widgets/control_panel.py (Part C 最终版 - 添加图表导出)

    # 在 _create_export_group 方法中修改：
  
    def _create_export_group(self):
        """✅ Part C: 创建导出功能组（数据 + 图表）"""
        group = QGroupBox("Data & Chart Export")
        layout = QVBoxLayout()
        
        # === 数据导出 ===
        data_label = QLabel("📊 Data Export:")
        data_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(data_label)
        
        data_export_layout = QHBoxLayout()
        
        self.export_csv_btn = QPushButton("CSV")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(lambda: self._export_results('csv'))
        self.export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover:enabled {
                background-color: #138d75;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        data_export_layout.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QPushButton("JSON")
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.clicked.connect(lambda: self._export_results('json'))
        self.export_json_btn.setStyleSheet(self.export_csv_btn.styleSheet())
        data_export_layout.addWidget(self.export_json_btn)
        
        self.export_excel_btn = QPushButton("Excel")
        self.export_excel_btn.setEnabled(False)
        self.export_excel_btn.clicked.connect(lambda: self._export_results('excel'))
        self.export_excel_btn.setStyleSheet(self.export_csv_btn.styleSheet())
        data_export_layout.addWidget(self.export_excel_btn)
        
        layout.addLayout(data_export_layout)
        
        # === 图表导出 ===
        chart_label = QLabel("📈 Chart Export:")
        chart_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 8px;")
        layout.addWidget(chart_label)
        
        chart_export_layout = QHBoxLayout()
        
        self.export_2d_btn = QPushButton("2D Map")
        self.export_2d_btn.setEnabled(False)
        self.export_2d_btn.clicked.connect(lambda: self._export_chart('2d'))
        self.export_2d_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover:enabled {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        chart_export_layout.addWidget(self.export_2d_btn)
        
        self.export_3d_btn = QPushButton("3D View")
        self.export_3d_btn.setEnabled(False)
        self.export_3d_btn.clicked.connect(lambda: self._export_chart('3d'))
        self.export_3d_btn.setStyleSheet(self.export_2d_btn.styleSheet())
        chart_export_layout.addWidget(self.export_3d_btn)
        
        self.export_both_btn = QPushButton("All Charts")
        self.export_both_btn.setEnabled(False)
        self.export_both_btn.clicked.connect(lambda: self._export_chart('both'))
        self.export_both_btn.setStyleSheet(self.export_2d_btn.styleSheet())
        chart_export_layout.addWidget(self.export_both_btn)
        
        layout.addLayout(chart_export_layout)
        
        # 导出格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Image Format:"))
        self.chart_format_combo = QComboBox()
        self.chart_format_combo.addItems(["PNG", "PDF", "SVG", "JPEG"])
        self.chart_format_combo.setCurrentText("PNG")
        format_layout.addWidget(self.chart_format_combo)
        
        format_layout.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" dpi")
        format_layout.addWidget(self.dpi_spin)
        layout.addLayout(format_layout)
        
        # 导出状态提示
        self.export_status_label = QLabel("💡 Run simulation to enable export")
        self.export_status_label.setStyleSheet("color: #7f8c8d; font-size: 9pt; margin-top: 5px;")
        self.export_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.export_status_label.setWordWrap(True)
        layout.addWidget(self.export_status_label)
        
        group.setLayout(layout)
        return group

    
    def _export_results(self, format_type):
        """✅ Part C: 导出结果"""
        if not self.current_results or not self.current_results.get('results'):
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type == 'csv':
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", f"simulation_results_{timestamp}.csv", "CSV Files (*.csv)"
            )
            if file_path:
                self._export_to_csv(file_path)
                
        elif format_type == 'json':
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export JSON", f"simulation_results_{timestamp}.json", "JSON Files (*.json)"
            )
            if file_path:
                self._export_to_json(file_path)
                
        elif format_type == 'excel':
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Excel", f"simulation_results_{timestamp}.xlsx", "Excel Files (*.xlsx)"
            )
            if file_path:
                self._export_to_excel(file_path)
    
    def _export_to_csv(self, file_path):
        """导出为CSV格式"""
        try:
            results = self.current_results['results']
            stats = self.current_results['stats']
            file_stats = self.current_results.get('file_stats', {})
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 写入元数据
                writer.writerow(['# Simulation Results Export'])
                writer.writerow(['# Export Time:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(['# Simulation Mode:', self.state.simulation_mode])
                writer.writerow(['# Scene:', self.state.current_scene])
                writer.writerow([])
                
                # 写入总体统计
                writer.writerow(['## Overall Statistics'])
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Points', stats['count']])
                writer.writerow(['RMSE (m)', f"{stats['rmse']:.4f}"])
                writer.writerow(['Mean Error (m)', f"{stats['mean']:.4f}"])
                writer.writerow(['Max Error (m)', f"{stats['max']:.4f}"])
                writer.writerow(['Min Error (m)', f"{stats['min']:.4f}"])
                writer.writerow([])
                
                # 写入分文件统计（如果有）
                if file_stats:
                    writer.writerow(['## Per-File Statistics'])
                    writer.writerow(['File', 'Points', 'RMSE', 'Mean', 'Max', 'Min'])
                    for filename, fstats in file_stats.items():
                        writer.writerow([
                            filename,
                            fstats['count'],
                            f"{fstats['rmse']:.4f}",
                            f"{fstats['mean']:.4f}",
                            f"{fstats['max']:.4f}",
                            f"{fstats['min']:.4f}"
                        ])
                    writer.writerow([])
                
                # 写入详细结果
                writer.writerow(['## Detailed Results'])
                writer.writerow([
                    'Index',
                    'Pixel_X', 'Pixel_Y',
                    'True_X', 'True_Y', 'True_Z',
                    'Planar_X', 'Planar_Y', 'Planar_Z',
                    'Error_m',
                    'Camera_X', 'Camera_Y', 'Camera_Z',
                    'Waypoint_Index',
                    'Source_File'
                ])
                
                for i, res in enumerate(results, 1):
                    writer.writerow([
                        i,
                        res['pixel'][0], res['pixel'][1],
                        f"{res['slope_projection'][0]:.3f}",
                        f"{res['slope_projection'][1]:.3f}",
                        f"{res['slope_projection'][2]:.3f}",
                        f"{res['planar_projection'][0]:.3f}",
                        f"{res['planar_projection'][1]:.3f}",
                        f"{res['planar_projection'][2]:.3f}",
                        f"{res['error_m']:.4f}",
                        f"{res['camera_pos'][0]:.3f}",
                        f"{res['camera_pos'][1]:.3f}",
                        f"{res['camera_pos'][2]:.3f}",
                        res.get('waypoint_index', 0),
                        res.get('source_file', 'N/A')
                    ])
            
            self.export_status_label.setText(f"✅ Exported:: {file_path}")
            self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
            print(f"✅ Results exported to CSV: {file_path}")
            
        except Exception as e:
            self.export_status_label.setText(f"❌ Export failed: {str(e)}")
            self.export_status_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            print(f"❌ Error exporting to CSV: {e}")
    
    def _export_to_json(self, file_path):
        """导出为JSON格式"""
        try:
            export_data = {
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'simulation_mode': self.state.simulation_mode,
                    'scene': self.state.current_scene,
                    'yolo_files': self.state.selected_yolo_files,
                    'max_detections_per_file': self.state.max_detections,
                    'reference_elevation_mode': self.state.ref_elevation_mode
                },
                'overall_statistics': self.current_results['stats'],
                'file_statistics': self.current_results.get('file_stats', {}),
                'results': self.current_results['results']
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.export_status_label.setText(f"✅  Exported: {file_path}")
            self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
            print(f"✅ Results exported to JSON: {file_path}")
            
        except Exception as e:
            self.export_status_label.setText(f"❌ Export failed: {str(e)}")
            self.export_status_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            print(f"❌ Error exporting to JSON: {e}")
    
    def _export_to_excel(self, file_path):
        """导出为Excel格式"""
        try:
            import pandas as pd
            
            results = self.current_results['results']
            stats = self.current_results['stats']
            file_stats = self.current_results.get('file_stats', {})
            
            # 创建 Excel Writer
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: 元数据
                metadata_df = pd.DataFrame({
                    'Parameter': [
                        'Export Time',
                        'Simulation Mode',
                        'Scene',
                        'YOLO Files',
                        'Max Detections/File',
                        'Reference Elevation Mode'
                    ],
                    'Value': [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        self.state.simulation_mode,
                        self.state.current_scene,
                        ', '.join(self.state.selected_yolo_files),
                        self.state.max_detections,
                        self.state.ref_elevation_mode
                    ]
                })
                metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
                
                # Sheet 2: 总体统计
                overall_stats_df = pd.DataFrame({
                    'Metric': ['Total Points', 'RMSE (m)', 'Mean Error (m)', 'Max Error (m)', 'Min Error (m)'],
                    'Value': [
                        stats['count'],
                        stats['rmse'],
                        stats['mean'],
                        stats['max'],
                        stats['min']
                    ]
                })
                overall_stats_df.to_excel(writer, sheet_name='Overall Statistics', index=False)
                
                # Sheet 3: 分文件统计
                if file_stats:
                    file_stats_data = []
                    for filename, fstats in file_stats.items():
                        file_stats_data.append({
                            'File': filename,
                            'Points': fstats['count'],
                            'RMSE': fstats['rmse'],
                            'Mean': fstats['mean'],
                            'Max': fstats['max'],
                            'Min': fstats['min']
                        })
                    file_stats_df = pd.DataFrame(file_stats_data)
                    file_stats_df.to_excel(writer, sheet_name='Per-File Statistics', index=False)
                
                # Sheet 4: 详细结果
                detailed_data = []
                for res in results:
                    detailed_data.append({
                        'Pixel_X': res['pixel'][0],
                        'Pixel_Y': res['pixel'][1],
                        'True_X': res['slope_projection'][0],
                        'True_Y': res['slope_projection'][1],
                        'True_Z': res['slope_projection'][2],
                        'Planar_X': res['planar_projection'][0],
                        'Planar_Y': res['planar_projection'][1],
                        'Planar_Z': res['planar_projection'][2],
                        'Error_m': res['error_m'],
                        'Camera_X': res['camera_pos'][0],
                        'Camera_Y': res['camera_pos'][1],
                        'Camera_Z': res['camera_pos'][2],
                        'Waypoint_Index': res.get('waypoint_index', 0),
                        'Source_File': res.get('source_file', 'N/A')
                    })
                detailed_df = pd.DataFrame(detailed_data)
                detailed_df.to_excel(writer, sheet_name='Detailed Results', index=False)
            
            self.export_status_label.setText(f"✅ Exported:{file_path}")
            self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
            print(f"✅ Results exported to Excel: {file_path}")
            
        except ImportError:
            self.export_status_label.setText("❌ pandas & openpyxl required")
            self.export_status_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            print("❌ Error: pandas or openpyxl not installed. Run: pip install pandas openpyxl")
        except Exception as e:
            self.export_status_label.setText(f"❌ Export failed: {str(e)}")
            self.export_status_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            print(f"❌ Error exporting to Excel: {e}")
    
    def update_results(self, results_data):
        """✅ Part C: 更新结果数据并启用导出按钮"""
        self.current_results = results_data
        
        # ✅ 修复：显式转换为布尔值
        has_results = bool(results_data and results_data.get('results'))
        
        # 数据导出按钮
        self.export_csv_btn.setEnabled(has_results)
        self.export_json_btn.setEnabled(has_results)
        self.export_excel_btn.setEnabled(has_results)
        
        # 图表导出按钮
        self.export_2d_btn.setEnabled(has_results)
        self.export_3d_btn.setEnabled(has_results)
        self.export_both_btn.setEnabled(has_results)
        
        if has_results:
            count = len(results_data['results'])
            self.export_status_label.setText(f"💾  Ready to export {count} results and charts")
            self.export_status_label.setStyleSheet("color: #2980b9; font-size: 9pt;")
        else:
            self.export_status_label.setText("💡 Run simulation to enable export")
            self.export_status_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")


    
    
    def _on_mode_changed(self, index):
        """
        ✅ 核心修复：此方法现在正确地接收索引（int）而不是文本（str）
        """
        # 从索引获取文本
        mode_text = self.mode_combo.itemText(index)
        is_trajectory = "trajectory" in mode_text
        
        # 切换控件显示/隐藏
        self.trajectory_widget.setVisible(is_trajectory)
        self.single_point_widget.setVisible(not is_trajectory)
        
        # 更新状态
        mode_key = "trajectory" if is_trajectory else "single_point"
        self.state.update_state(simulation_mode=mode_key)
    def _on_yolo_assoc_changed(self, index):
        # ✅ 新增: YOLO关联模式切换逻辑
        mode_text = self.yolo_assoc_combo.itemText(index)
        mode_key = "cycle" if "Cycle" in mode_text else "fixed"
        self.state.update_state(yolo_association_mode=mode_key)
        
    def _update_sensor_size(self):
        # ✅ 新增: 更新传感器尺寸
        size = [self.sensor_w_spin.value(), self.sensor_h_spin.value()]
        self.state.update_state(sensor_size_px=size)

    def _select_yolo_files(self):
        """选择多个YOLO文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select YOLO Detection Files (Multi-select)",
            self.state.yolo_dataset_dir,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if files:
            # 提取文件名（不含路径）
            file_names = [os.path.basename(file) for file in files]
            
            # 更新状态
            self.state.update_state(selected_yolo_files=file_names)
            
            # 更新UI列表
            self._update_file_list(file_names)
    
    def _clear_yolo_files(self):
        """清空YOLO文件列表"""
        self.state.update_state(selected_yolo_files=[])
        self.yolo_file_list.clear()
    
    def _update_file_list(self, file_names):
        """更新文件列表显示"""
        self.yolo_file_list.clear()
        for i, file_name in enumerate(file_names, 1):
            item = QListWidgetItem(f"{i}. {file_name}")
            self.yolo_file_list.addItem(item)
    
    def set_available_yolo_files(self, file_list):
        """兼容性方法：为app.py提供向后兼容"""
        pass
    
    def update_controls_from_state(self):
        """✅ 修复：确保所有映射和调用都使用正确的显示名称"""
        # 场景
        scene_text_map = {
            "complex_terrain": "complex_terrain",
            "virtual_slope": "virtual_slope",
            "large_terrain": "🌍 large_terrain" 
        }
        self.scene_combo.setCurrentText(scene_text_map[self.state.current_scene])
        self.slope_spin.setValue(self.state.virtual_slope_angle)
        # ✅ 更新超大地形参数
        if hasattr(self, 'terrain_size_spin'):
            self.terrain_size_spin.setValue(self.state.large_terrain_size_km)
            self.terrain_res_spin.setValue(self.state.large_terrain_resolution_m)
        
        # 手动触发显示/隐藏逻辑
        self._on_scene_changed(self.scene_combo.currentIndex())

        # 模式
        mode_text_map = {
            "single_point": "single_point",
            "trajectory": "trajectory"
        }
        self.mode_combo.setCurrentText(mode_text_map[self.state.simulation_mode])
        # ✅ 手动触发显示/隐藏逻辑（传递当前索引）
        self._on_mode_changed(self.mode_combo.currentIndex())

        # 相机参数
        self.focal_length_spin.setValue(self.state.focal_length_px)
        self.sensor_w_spin.setValue(self.state.sensor_size_px[0])
        self.sensor_h_spin.setValue(self.state.sensor_size_px[1])
        
        # YOLO
        self._update_file_list(self.state.selected_yolo_files)
        assoc_text_map = { "fixed": "Fixed", "cycle": "Cycle" }
        self.yolo_assoc_combo.setCurrentText(assoc_text_map[self.state.yolo_association_mode])
        self.random_sample_check.setChecked(self.state.random_sample)
        self.max_detections.setValue(self.state.max_detections)
        if hasattr(self, 'traj_roll'):  # 检查控件是否存在
            traj_att = self.state.trajectory_attitude
            self.traj_roll.setValue(traj_att.get('roll', 0))
            self.traj_pitch.setValue(traj_att.get('pitch', -30))
            
            is_auto_yaw = isinstance(traj_att.get('yaw'), str) and traj_att['yaw'].lower() == 'auto'
            self.auto_yaw_check.setChecked(is_auto_yaw)
            
            if not is_auto_yaw:
                self.traj_yaw.setValue(traj_att.get('yaw', 0))
        
        # ✅ 新增：更新航线路径显示
        if hasattr(self, 'start_x') and len(self.state.trajectory_path) >= 2:
            self.start_x.setValue(self.state.trajectory_path[0]['x'])
            self.start_y.setValue(self.state.trajectory_path[0]['y'])
            self.end_x.setValue(self.state.trajectory_path[1]['x'])
            self.end_y.setValue(self.state.trajectory_path[1]['y'])
        
        # ✅ 关键修复：更新单点模式的位置和姿态显示
        if hasattr(self, 'pos_x'):
            self.pos_x.blockSignals(True)
            self.pos_y.blockSignals(True)
            self.pos_z.blockSignals(True)
            self.roll.blockSignals(True)
            self.pitch.blockSignals(True)
            self.yaw.blockSignals(True)
            
            self.pos_x.setValue(self.state.camera_position[0])
            self.pos_y.setValue(self.state.camera_position[1])
            self.pos_z.setValue(self.state.camera_position[2])
            
            self.roll.setValue(self.state.camera_attitude['roll'])
            self.pitch.setValue(self.state.camera_attitude['pitch'])
            self.yaw.setValue(self.state.camera_attitude['yaw'])
            
            self.pos_x.blockSignals(False)
            self.pos_y.blockSignals(False)
            self.pos_z.blockSignals(False)
            self.roll.blockSignals(False)
            self.pitch.blockSignals(False)
            self.yaw.blockSignals(False)
        if hasattr(self, 'ref_mode_combo'):
            ref_mode_map = {
                "camera_nadir": "camera_nadir",
                "custom_value": "custom_value"
            }
            self.ref_mode_combo.setCurrentText(ref_mode_map[self.state.ref_elevation_mode])
            self.custom_ref.setValue(self.state.custom_ref_elevation)
            
            # 手动触发UI更新
            self._on_ref_mode_changed(self.ref_mode_combo.currentText())

    def _export_chart(self, chart_type):
        """✅ 导出图表"""
        if not hasattr(self, 'parent_window') or self.parent_window is None:
            print("⚠️ Warning: Parent window not set, cannot export charts")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fmt = self.chart_format_combo.currentText().lower()
        dpi = self.dpi_spin.value()
        
        if chart_type == '2d':
            default_name = f"2D_map_{timestamp}.{fmt}"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export 2D Map", default_name, 
                f"{fmt.upper()} Files (*.{fmt});;All Files (*)"
            )
            if file_path:
                self.parent_window.export_2d_chart(file_path, dpi)
                self.export_status_label.setText(f"✅ 2D Map exported: {os.path.basename(file_path)}")
                self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
        
        elif chart_type == '3d':
            default_name = f"3D_view_{timestamp}.{fmt}"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export 3D View", default_name,
                f"{fmt.upper()} Files (*.{fmt});;All Files (*)"
            )
            if file_path:
                self.parent_window.export_3d_chart(file_path, dpi)
                self.export_status_label.setText(f"✅ 3D View exported: {os.path.basename(file_path)}")
                self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
        
        elif chart_type == 'both':
            folder = QFileDialog.getExistingDirectory(self, "Select Save Folder")
            if folder:
                file_2d = os.path.join(folder, f"2D_map_{timestamp}.{fmt}")
                file_3d = os.path.join(folder, f"3D_view_{timestamp}.{fmt}")
                
                self.parent_window.export_2d_chart(file_2d, dpi)
                self.parent_window.export_3d_chart(file_3d, dpi)
                
                self.export_status_label.setText(f"✅ Exported to: {folder}")
                self.export_status_label.setStyleSheet("color: #27ae60; font-size: 9pt;")
