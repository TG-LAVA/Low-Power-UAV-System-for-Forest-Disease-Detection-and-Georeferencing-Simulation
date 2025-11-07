# gui/widgets/trajectory_panel.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                             QDoubleSpinBox, QComboBox, QLabel, QHBoxLayout,
                             QPushButton)
from PyQt6.QtCore import Qt

class TrajectoryPanel(QWidget):
    def __init__(self, state_manager, control_panel): # 接收 control_panel
        super().__init__()
        self.state = state_manager
        self.control_panel = control_panel # 保存引用
        self._init_ui()
        self._connect_signals()
        self.update_controls_from_state()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 5)

        path_group = QGroupBox("Path")
        path_layout = QFormLayout()
        
        self.start_x, self.start_y = QDoubleSpinBox(), QDoubleSpinBox()
        self._setup_coord_spinbox(self.start_x)
        self._setup_coord_spinbox(self.start_y)
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("X:"))
        start_layout.addWidget(self.start_x)
        start_layout.addWidget(QLabel("Y:"))
        start_layout.addWidget(self.start_y)
        path_layout.addRow("Start Point:", start_layout)

        self.end_x, self.end_y = QDoubleSpinBox(), QDoubleSpinBox()
        self._setup_coord_spinbox(self.end_x)
        self._setup_coord_spinbox(self.end_y)
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("X:"))
        end_layout.addWidget(self.end_x)
        end_layout.addWidget(QLabel("Y:"))
        end_layout.addWidget(self.end_y)
        path_layout.addRow("End Point:", end_layout)

        # ✅ 4. 添加绘制按钮
        self.draw_button = QPushButton("✏️ Draw on Map")
        self.draw_button.setObjectName("draw_button") # 用于应用样式
        path_layout.addRow(self.draw_button)

        path_group.setLayout(path_layout)
        main_layout.addWidget(path_group)

        flight_group = QGroupBox("Flight Parameters")
        flight_layout = QFormLayout()
        self.altitude_agl = QDoubleSpinBox()
        self.altitude_agl.setRange(10.0, 10000.0)
        self.altitude_agl.setSuffix(" m (AGL)")
        flight_layout.addRow("Altitude (AGL):", self.altitude_agl)
        self.photo_interval = QDoubleSpinBox()
        self.photo_interval.setRange(10.0, 5000.0)
        self.photo_interval.setSuffix(" m")
        flight_layout.addRow("Photo Interval:", self.photo_interval)
        flight_group.setLayout(flight_layout)
        main_layout.addWidget(flight_group)

        attitude_group = QGroupBox("Camera Attitude")
        attitude_layout = QVBoxLayout()
        self.attitude_mode = QComboBox()
        self.attitude_mode.addItems(["Fixed", "Auto Yaw"])
        attitude_layout.addWidget(self.attitude_mode)
        
        self.fixed_attitude_widget = QWidget()
        form_layout = QFormLayout(self.fixed_attitude_widget)
        form_layout.setContentsMargins(0, 5, 0, 0)
        self.roll_spinbox = self._create_attitude_spinbox()
        self.pitch_spinbox = self._create_attitude_spinbox()
        self.yaw_spinbox = self._create_attitude_spinbox()
        form_layout.addRow("Roll:", self.roll_spinbox)
        form_layout.addRow("Pitch:", self.pitch_spinbox)
        form_layout.addRow("Yaw:", self.yaw_spinbox)
        attitude_layout.addWidget(self.fixed_attitude_widget)
        attitude_group.setLayout(attitude_layout)
        main_layout.addWidget(attitude_group)

    def _setup_coord_spinbox(self, spinbox):
        spinbox.setRange(0, 10_000_000)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(100)
        spinbox.setGroupSeparatorShown(True)

    def _create_attitude_spinbox(self):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(-180.0, 180.0)
        spinbox.setDecimals(1)
        spinbox.setSuffix(" °")
        return spinbox

    def _connect_signals(self):
        self.start_x.valueChanged.connect(self._update_state)
        self.start_y.valueChanged.connect(self._update_state)
        self.end_x.valueChanged.connect(self._update_state)
        self.end_y.valueChanged.connect(self._update_state)
        self.altitude_agl.valueChanged.connect(self._update_state)
        self.photo_interval.valueChanged.connect(self._update_state)
        self.attitude_mode.currentIndexChanged.connect(self._update_state)
        self.roll_spinbox.valueChanged.connect(self._update_state)
        self.pitch_spinbox.valueChanged.connect(self._update_state)
        self.yaw_spinbox.valueChanged.connect(self._update_state)
        self.attitude_mode.currentIndexChanged.connect(self._on_attitude_mode_changed)
        # ✅ 4. 连接绘制按钮信号到 control_panel 的信号
        self.draw_button.clicked.connect(self.control_panel.draw_trajectory_requested)

    def _on_attitude_mode_changed(self, index):
        self.fixed_attitude_widget.setVisible(self.attitude_mode.currentText() == "Fixed")

    def _update_state(self):
        path = [{'x': self.start_x.value(), 'y': self.start_y.value()}, {'x': self.end_x.value(), 'y': self.end_y.value()}]
        attitude = {
            'roll': self.roll_spinbox.value(),
            'pitch': self.pitch_spinbox.value(),
            'yaw': self.yaw_spinbox.value() if self.attitude_mode.currentText() == "Fixed" else "auto"
        }
        self.state.update_state(
            trajectory_path=path,
            flight_altitude_agl=self.altitude_agl.value(),
            photo_interval_meters=self.photo_interval.value(),
            trajectory_attitude=attitude,
            trigger_recalc=False # 参数调整不触发计算
        )
    
    def update_controls_from_state(self):
        # 相同逻辑，保持不变
        for widget in self.findChildren(QWidget): widget.blockSignals(True)
        try:
            path = self.state.trajectory_path
            if len(path) >= 2:
                self.start_x.setValue(path[0]['x'])
                self.start_y.setValue(path[0]['y'])
                self.end_x.setValue(path[1]['x'])
                self.end_y.setValue(path[1]['y'])
            self.altitude_agl.setValue(self.state.flight_altitude_agl)
            self.photo_interval.setValue(self.state.photo_interval_meters)
            attitude = self.state.trajectory_attitude
            is_auto_yaw = isinstance(attitude.get('yaw'), str) and attitude['yaw'].lower() == 'auto'
            self.attitude_mode.setCurrentText("Auto Yaw" if is_auto_yaw else "Fixed")
            self.fixed_attitude_widget.setVisible(not is_auto_yaw)
            if not is_auto_yaw:
                self.yaw_spinbox.setValue(attitude.get('yaw', 0.0))
            self.roll_spinbox.setValue(attitude.get('roll', 0.0))
            self.pitch_spinbox.setValue(attitude.get('pitch', 0.0))
        finally:
            for widget in self.findChildren(QWidget): widget.blockSignals(False)
