# -*- coding: utf-8 -*-
import sys
import math
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

# ===== 后端 =====
from services.simulation_service import run_simulation_job, get_job_info
from services.result_service import get_series_data
from services.export_service import export_job_data

matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


def config_spin(spin, minv, maxv, val, dec=3, step=1.0, suffix=""):
    spin.setRange(minv, maxv)
    spin.setDecimals(dec)
    spin.setSingleStep(step)
    spin.setValue(val)
    if suffix:
        spin.setSuffix(suffix)


def config_line(edit, text=""):
    edit.setText(text)


class AtmosOrbitApp(QWidget):
    def __init__(self):
        super().__init__()
        self.current_job_id = None
        self.hover_artists = []  # 用于追踪 hover 相关的图形元素

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_status)

    # ==========================================
    # UI
    # ==========================================
    def init_ui(self):
        self.setWindowTitle("🛰️ AtmosOrbitSim V4.0")
        self.resize(1400, 850)

        main = QHBoxLayout()

        # ================= 左侧 =================
        left_panel = QWidget()
        left = QVBoxLayout(left_panel)

        # ===== 模型 =====
        self.model = QComboBox()
        self.model.addItems(["HPOP", "SGP4", "ANALYTICAL", "TWOBODY"])
        self.model.currentTextChanged.connect(self.update_model)

        form = QFormLayout()
        form.addRow("模型", self.model)

        # ===== 仿真参数 =====
        self.epoch_iso = QLineEdit()
        self.duration_sec = QDoubleSpinBox()
        self.step_sec = QDoubleSpinBox()

        config_line(self.epoch_iso, "2026-05-01T12:00:00.000Z")
        config_spin(self.duration_sec, 1.0, 1e7, 5400.0, 1, 1.0, " s")
        config_spin(self.step_sec, 0.1, 1000.0, 1.0, 1, 0.1, " s")

        form.addRow("仿真历元", self.epoch_iso)
        form.addRow("仿真时长", self.duration_sec)
        form.addRow("仿真步长", self.step_sec)

        # ===== 六根数 =====
        self.a = QDoubleSpinBox()
        self.e = QDoubleSpinBox()
        self.i = QDoubleSpinBox()
        self.raan = QDoubleSpinBox()
        self.arg_pe = QDoubleSpinBox()
        self.m0 = QDoubleSpinBox()

        config_spin(self.a, 6e6, 8e6, 6878137.0, 1, suffix=" m")
        config_spin(self.e, 0, 0.1, 0.001, 6)
        config_spin(self.i, 0, 180, 97.5, 3, suffix=" °")
        config_spin(self.raan, 0, 360, 30, 3, suffix=" °")
        config_spin(self.arg_pe, 0, 360, 90, 3, suffix=" °")
        config_spin(self.m0, 0, 360, 0, 3, suffix=" °")

        form.addRow("半长轴", self.a)
        form.addRow("离心率", self.e)
        form.addRow("轨道倾角", self.i)
        form.addRow("升交点赤经", self.raan)
        form.addRow("近地点幅角", self.arg_pe)
        form.addRow("平近点角", self.m0)

        # ===== TLE =====
        self.tle1 = QTextEdit()
        self.tle2 = QTextEdit()
        form.addRow("两行根数行1", self.tle1)
        form.addRow("两行根数行2", self.tle2)

        # ===== 物理 =====
        self.mass = QDoubleSpinBox()
        self.area = QDoubleSpinBox()
        self.cd = QDoubleSpinBox()
        self.cr = QDoubleSpinBox()

        config_spin(self.mass, 100, 5000, 1200, 1, suffix=" kg")
        config_spin(self.area, 0.1, 20, 6.5, 2, suffix=" m²")
        config_spin(self.cd, 0.5, 5, 2.2, 2)
        config_spin(self.cr, 0.5, 3, 1.2, 2)

        form.addRow("质量", self.mass)
        form.addRow("对风面积", self.area)
        form.addRow("阻力系数", self.cd)
        form.addRow("压辐射系数", self.cr)

        # ===== 摄动 =====
        self.gravity_degree = QSpinBox()
        self.gravity_order = QSpinBox()
        self.thirdbody = QCheckBox("ThirdBody")
        self.drag = QCheckBox("Drag")
        self.srp = QCheckBox("SRP")

        self.gravity_degree.setRange(0, 100)
        self.gravity_order.setRange(0, 100)
        self.gravity_degree.setValue(21)
        self.gravity_order.setValue(21)

        self.thirdbody.setChecked(True)
        self.drag.setChecked(True)
        self.srp.setChecked(False)

        self.thirdbody.stateChanged.connect(self.update_thirdbody)
        self.drag.stateChanged.connect(self.update_drag)
        self.srp.stateChanged.connect(self.update_srp)

        form.addRow("重力模型阶数", self.gravity_degree)
        form.addRow("重力模型次数", self.gravity_order)
        self.thirdbody.setText("三体摄动")
        self.drag.setText("大气阻力")
        self.srp.setText("太阳辐射压")
        form.addRow(self.thirdbody)
        form.addRow(self.drag)
        form.addRow(self.srp)

        left.addLayout(form)

        # ===== 光学 =====
        optics = QGroupBox("光学")
        ol = QFormLayout()

        self.fov_mode = QComboBox()
        self.fov_mode.addItems(["视场角模式", "焦距模式"])
        self.fov_mode.currentTextChanged.connect(self.update_fov)

        self.fov = QDoubleSpinBox()
        self.focal = QDoubleSpinBox()
        self.sensor = QDoubleSpinBox()

        # 相机安装角（默认与配置文件一致）
        self.mount_roll = QDoubleSpinBox()
        self.mount_pitch = QDoubleSpinBox()
        self.mount_yaw = QDoubleSpinBox()

        config_spin(self.fov, 0.1, 60, 2, 2, suffix=" °")
        config_spin(self.focal, 10, 5000, 2000, 1, suffix=" mm")
        config_spin(self.sensor, 1, 100, 32.5, 2, suffix=" mm")
        config_spin(self.mount_roll, -180, 180, 68.0, 2, suffix=" °")
        config_spin(self.mount_pitch, -180, 180, 0.0, 2, suffix=" °")
        config_spin(self.mount_yaw, -180, 180, 0.0, 2, suffix=" °")

        ol.addRow("模式", self.fov_mode)
        ol.addRow("视场角", self.fov)
        ol.addRow("焦距", self.focal)
        ol.addRow("传感器尺寸", self.sensor)
        ol.addRow("安装滚转角", self.mount_roll)
        ol.addRow("安装俯仰角", self.mount_pitch)
        ol.addRow("安装偏航角", self.mount_yaw)

        optics.setLayout(ol)
        left.addWidget(optics)

        # ===== 姿态 =====
        att = QGroupBox("姿态")
        al = QFormLayout()

        self.mode = QComboBox()
        self.mode.addItems(["动态控制", "固定锁定"])
        self.mode.currentTextChanged.connect(self.update_att)

        self.target = QDoubleSpinBox()
        self.locked = QDoubleSpinBox()
        self.use_target = QRadioButton("使用目标高度")
        self.use_locked = QRadioButton("使用锁定角")
        self.enable_noise = QCheckBox("启用姿态噪声")
        self.drift_rate = QDoubleSpinBox()
        self.jitter_3sigma = QDoubleSpinBox()

        config_spin(self.target, 100, 1000, 400, 1, suffix=" km")
        config_spin(self.locked, -90, 90, 68, 2, suffix=" °")
        self.use_target.setChecked(True)
        self.use_locked.setChecked(False)
        self.use_target.toggled.connect(self.update_att)
        config_spin(self.drift_rate, 0.0, 10.0, 0.05, 3, 0.01, " arcsec/s")
        config_spin(self.jitter_3sigma, 0.0, 100.0, 1.5, 2, 0.1, " arcsec")
        self.enable_noise.stateChanged.connect(self.update_noise_perturbation)

        al.addRow("控制模式", self.mode)
        al.addRow(self.use_target)
        al.addRow("  目标高度", self.target)
        al.addRow(self.use_locked)
        al.addRow("  锁定角", self.locked)
        al.addRow(self.enable_noise)
        al.addRow("姿态漂移速率", self.drift_rate)
        al.addRow("姿态抖动3σ", self.jitter_3sigma)

        att.setLayout(al)
        left.addWidget(att)

        # ===== 控制 =====
        self.btn = QPushButton("🚀 启动")
        self.btn.clicked.connect(self.run)

        self.progress = QProgressBar()
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.export = QPushButton("导出")
        self.export.setEnabled(False)
        self.export.clicked.connect(self.export_data)

        left.addWidget(self.btn)
        left.addWidget(self.progress)
        left.addWidget(self.log)
        left.addWidget(self.export)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_panel)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ================= 右侧 =================
        right = QVBoxLayout()
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        right.addWidget(self.canvas)

        main.addWidget(left_scroll, 1)
        main.addLayout(right, 3)
        self.setLayout(main)

        self.update_model()
        self.update_drag()
        self.update_srp()
        self.update_fov()
        self.update_att()
        self.update_noise_perturbation()

    # ==========================================
    # UI联动
    # ==========================================
    def update_model(self):
        sgp4 = self.model.currentText() == "SGP4"
        for w in [self.a, self.e, self.i, self.raan, self.arg_pe, self.m0]:
            w.setEnabled(not sgp4)
        self.tle1.setEnabled(sgp4)
        self.tle2.setEnabled(sgp4)

        model = self.model.currentText()
        is_hpop = model == "HPOP"
        is_analytical = model == "ANALYTICAL"
        is_hpop_or_analytical = is_hpop or is_analytical
        
        # 质量和重力只在 HPOP 和 ANALYTICAL 时启用
        self.mass.setEnabled(is_hpop_or_analytical)
        self.gravity_degree.setEnabled(is_hpop_or_analytical)
        
        # gravity_degree 范围：ANALYTICAL 最大 5，HPOP 最大 21
        if is_analytical:
            self.gravity_degree.setMaximum(5)
            if self.gravity_degree.value() > 5:
                self.gravity_degree.setValue(5)
        elif is_hpop:
            self.gravity_degree.setMaximum(21)
        
        # gravity_order、thirdbody、drag、srp 只在 HPOP 时启用
        self.gravity_order.setEnabled(is_hpop)
        self.thirdbody.setEnabled(is_hpop)
        self.drag.setEnabled(is_hpop)
        self.srp.setEnabled(is_hpop)
        # 对风面积在drag或srp任一启用时可用
        self.area.setEnabled(is_hpop and (self.drag.isChecked() or self.srp.isChecked()))
        self.cd.setEnabled(is_hpop and self.drag.isChecked())
        self.cr.setEnabled(is_hpop and self.srp.isChecked())

    def update_drag(self):
        self.cd.setEnabled(self.drag.isChecked())
        self.update_area_state()

    def update_thirdbody(self):
        # 预留联动入口：目前 thirdbody 仅作为开关入参
        pass

    def update_srp(self):
        self.cr.setEnabled(self.srp.isChecked())
        self.update_area_state()

    def update_area_state(self):
        """对风面积在drag或srp任一启用时可用"""
        is_hpop = self.model.currentText() == "HPOP"
        area_needed = is_hpop and (self.drag.isChecked() or self.srp.isChecked())
        self.area.setEnabled(area_needed)

    def update_fov(self):
        f = self.fov_mode.currentText() == "视场角模式"
        self.fov.setEnabled(f)
        self.focal.setEnabled(not f)
        self.sensor.setEnabled(not f)

    def update_att(self):
        dyn = self.mode.currentText() == "动态控制"
        
        if dyn:
            # 动态控制：只能使用目标高度
            self.use_target.setEnabled(False)
            self.use_locked.setEnabled(False)
            self.use_target.setChecked(True)
            self.use_locked.setChecked(False)
            self.target.setEnabled(True)
            self.locked.setEnabled(False)
        else:
            # 固定锁定：两个选项都可用，根据单选框状态
            self.use_target.setEnabled(True)
            self.use_locked.setEnabled(True)
            self.target.setEnabled(self.use_target.isChecked())
            self.locked.setEnabled(self.use_locked.isChecked())

    def update_noise_perturbation(self):
        enabled = self.enable_noise.isChecked()
        self.drift_rate.setEnabled(enabled)
        self.jitter_3sigma.setEnabled(enabled)

    # ==========================================
    # Payload
    # ==========================================
    def build_payload(self):
        model = self.model.currentText()
        is_hpop = model == "HPOP"
        is_analytical = model == "ANALYTICAL"
        
        # 根据模型类型构建 perturbations
        if is_hpop:
            perturbations = {
                "gravity_degree": self.gravity_degree.value(),
                "gravity_order": self.gravity_order.value(),
                "enable_thirdbody": self.thirdbody.isChecked(),
                "enable_drag": self.drag.isChecked(),
                "enable_srp": self.srp.isChecked()
            }
        elif is_analytical:
            perturbations = {
                "gravity_degree": self.gravity_degree.value()
            }
        else:
            perturbations = {}

        return {
            "orbit_propagation": {
                "model": model,
                "epoch_iso": self.epoch_iso.text().strip() or None,
                "duration_sec": self.duration_sec.value(),
                "step_sec": self.step_sec.value(),
                "a": self.a.value(),
                "e": self.e.value(),
                "i": self.i.value(),
                "raan": self.raan.value(),
                "arg_pe": self.arg_pe.value(),
                "m0": self.m0.value(),
                "tle_line1": self.tle1.toPlainText() or None,
                "tle_line2": self.tle2.toPlainText() or None,
                "mass_kg": self.mass.value() if is_hpop or is_analytical else None,
                "cross_section_m2": self.area.value() if (is_hpop and (self.drag.isChecked() or self.srp.isChecked())) else None,
                "cd": self.cd.value() if (is_hpop and self.drag.isChecked()) else None,
                "cr": self.cr.value() if (is_hpop and self.srp.isChecked()) else None,
                "perturbations": perturbations
            },
            "payload_optics": {
                "fov_deg": self.fov.value() if self.fov_mode.currentText() == "视场角模式" else None,
                "focal_length_mm": self.focal.value() if self.fov_mode.currentText() != "视场角模式" else None,
                "sensor_size_mm": self.sensor.value() if self.fov_mode.currentText() != "视场角模式" else None,
                "mounting_angles": {
                    "mount_roll_deg": self.mount_roll.value(),
                    "mount_pitch_deg": self.mount_pitch.value(),
                    "mount_yaw_deg": self.mount_yaw.value()
                }
            },
            "attitude_control": {
                "mode": "DYNAMIC" if self.mode.currentText()=="动态控制" else "LOCKED",
                "target_alt_km": self.target.value() if self.use_target.isChecked() else None,
                "locked_angle_deg": self.locked.value() if self.use_locked.isChecked() else None,
                "perturbations": {
                    "enable_noise": self.enable_noise.isChecked(),
                    "drift_rate_arcsec_s": self.drift_rate.value(),
                    "jitter_3sigma_arcsec": self.jitter_3sigma.value()
                }
            }
        }

    # ==========================================
    # 运行
    # ==========================================
    def run(self):
        payload = self.build_payload()
        self.current_job_id = run_simulation_job(payload)
        self.log.append(f"任务提交: {self.current_job_id}")
        self.timer.start(200)

    def check_status(self):
        info = get_job_info(self.current_job_id)
        if info["status"] == "RUNNING":
            pct = int(info["current"] / info["total"] * 100)
            self.progress.setValue(pct)
        elif info["status"] == "SUCCESS":
            self.timer.stop()
            self.progress.setValue(100)
            self.render()
        elif info["status"] == "FAILED":
            self.timer.stop()
            self.progress.setValue(0)
            self.log.append(f"❌ 任务失败: {info.get('msg', '未知错误')}")
            self.export.setEnabled(False)
        elif info["status"] == "NOT_FOUND":
            self.timer.stop()
            self.progress.setValue(0)
            self.log.append("❌ 任务不存在或已丢失")

    # ==========================================
    # 画图（完全保留你原版）
    # ==========================================
    def render(self):
        data = get_series_data(self.current_job_id, [
            "sat_lon","sat_lat","tangent_lon","tangent_lat","sat_in_eclipse","tangent_in_eclipse","tangent_alt_km",
            "fov_alt_min_km","fov_alt_max_km",
            "sat_roll_deg","sat_pitch_deg","sat_yaw_deg",
            "attitude_noise_deg","sat_alt_km","slant_range_km"
        ])

        t = data["time"]
        s = data["series"]

        # 使用后端返回的语义化字段（生产端已修正）。绘图仍做一次上下界有序化，
        # 以防个别点异常导致 fill_between 反向
        fov_min_sem = s.get("fov_alt_min_km", [])
        fov_max_sem = s.get("fov_alt_max_km", [])
        fov_low = [min(a, b) for a, b in zip(fov_min_sem, fov_max_sem)]
        fov_high = [max(a, b) for a, b in zip(fov_min_sem, fov_max_sem)]
        # 保存供 hover 使用，优先使用已排序的视场上下界
        self.fov_low = fov_low
        self.fov_high = fov_high

        self.figure.clear()
        self.figure.set_facecolor("#fbfbfd")
        self.figure.suptitle(
            f"AtmosOrbitSim V4.0 仿真仪表板（任务: {self.current_job_id}）",
            fontsize=16,
            fontweight="bold"
        )

        ax1 = self.figure.add_subplot(221)
        axes_list = [ax1]  # 用于保存四个主子图
        sat_eclipse = [bool(v) for v in s.get("sat_in_eclipse", [])]
        tang_eclipse = [bool(v) for v in s.get("tangent_in_eclipse", [])]
        tang_step = max(1, len(s.get("sat_lon", [])) // 400)
        
        if sat_eclipse and tang_eclipse and len(sat_eclipse) == len(s["sat_lon"]):
            # 分四种状态：卫星地影、切点地影、都在、都不在
            both_sun = {"sat": [], "tang": []}
            sat_ecl_only = {"sat": [], "tang": []}
            tang_ecl_only = {"sat": [], "tang": []}
            both_ecl = {"sat": [], "tang": []}
            
            for i, (sat_lon, sat_lat, tang_lon, tang_lat) in enumerate(zip(
                s["sat_lon"], s["sat_lat"], s.get("tangent_lon", []), s.get("tangent_lat", [])
            )):
                sat_ec = sat_eclipse[i] if i < len(sat_eclipse) else False
                tan_ec = tang_eclipse[i] if i < len(tang_eclipse) else False
                
                # 卫星
                if not sat_ec and not tan_ec:
                    both_sun["sat"].append((sat_lon, sat_lat))
                elif sat_ec and tan_ec:
                    both_ecl["sat"].append((sat_lon, sat_lat))
                elif sat_ec:
                    sat_ecl_only["sat"].append((sat_lon, sat_lat))
                else:
                    tang_ecl_only["sat"].append((sat_lon, sat_lat))
                
                # 切点
                if not sat_ec and not tan_ec:
                    both_sun["tang"].append((tang_lon, tang_lat))
                elif sat_ec and tan_ec:
                    both_ecl["tang"].append((tang_lon, tang_lat))
                elif sat_ec:
                    sat_ecl_only["tang"].append((tang_lon, tang_lat))
                else:
                    tang_ecl_only["tang"].append((tang_lon, tang_lat))
            
            # 画四种状态，每种都有卫星(o)和切点(*)
            colors = ["#13c2c2", "#fa8c16", "#f59e0b", "#f5222d"]
            labels = ["卫星/切点均日照", "仅卫星地影", "仅切点地影", "卫星/切点均地影"]
            categories = [both_sun, sat_ecl_only, tang_ecl_only, both_ecl]
            
            for color, label, cat in zip(colors, labels, categories):
                # 卫星 (圆点)
                if cat["sat"]:
                    lons, lats = zip(*cat["sat"])
                    ax1.scatter(lons, lats, c=color, s=10, alpha=0.55, marker='o', edgecolors='none', zorder=2)
                # 切点 (叉号，抽样显示，避免过密)
                if cat["tang"]:
                    sampled = cat["tang"][::tang_step]
                    lons, lats = zip(*sampled)
                    ax1.scatter(lons, lats, c=color, s=36, alpha=0.95, marker='x', linewidths=1.1, zorder=3)
            
            # 手工添加图例
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='#13c2c2', markersize=6, label="卫星/切点均日照"),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='#fa8c16', markersize=6, label="仅卫星地影"),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='#f59e0b', markersize=6, label="仅切点地影"),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='#f5222d', markersize=6, label="卫星/切点均地影"),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=6, label="◎ 卫星"),
                Line2D([0], [0], marker='x', color='gray', markersize=8, linewidth=0, label="× 切点(抽样)")
            ]
            ax1.legend(handles=legend_elements, loc="upper right", frameon=False, fontsize=7)
        else:
            ax1.scatter(s["sat_lon"], s["sat_lat"], c="#13c2c2", s=8, alpha=0.7, marker='o', label="卫星")
            if "tangent_lon" in s and "tangent_lat" in s:
                ax1.scatter(s["tangent_lon"][::tang_step], s["tangent_lat"][::tang_step], c="#13c2c2", s=30, alpha=0.95, marker='x', linewidths=1.1, label="切点(抽样)")
            ax1.legend(loc="upper right", frameon=False, fontsize=8)
        ax1.set_title("1. 地球覆盖轨迹图")
        ax1.set_xlim(-180, 180)
        ax1.set_ylim(-90, 90)
        ax1.set_xlabel("经度（度）")
        ax1.set_ylabel("纬度（度）")
        ax1.grid(True, linestyle="--", alpha=0.35)

        ax2 = self.figure.add_subplot(222)
        axes_list.append(ax2)
        ax2.set_title("2. 载荷视场与光照分析面板")
        ax2.fill_between(t, fov_low, fov_high, color="#fa8c16", alpha=0.25, label="视场覆盖带")
        ax2.plot(t, s["tangent_alt_km"], color="#f5222d", linewidth=2, label="靶心高度")
        ax2.set_xlabel("时间（秒）")
        ax2.set_ylabel("高度（km）")
        ax2.legend(loc="upper right", frameon=False)
        ax2.grid(True, alpha=0.3)

        ax3 = self.figure.add_subplot(223)
        axes_list.append(ax3)
        ax3.set_title("3. 姿态机动与噪声控制面板")
        line1 = ax3.plot(t, s["sat_roll_deg"], label="滚转角", color="tab:blue", linewidth=1.5)
        line2 = ax3.plot(t, s["sat_pitch_deg"], label="俯仰角", color="tab:green", linewidth=1.5)
        line3 = ax3.plot(t, s["sat_yaw_deg"], label="偏航角", color="tab:purple", linewidth=1.5)
        ax3.set_xlabel("时间（秒）")
        ax3.set_ylabel("姿态角（度）")
        ax3.grid(True, alpha=0.3)

        ax3_twin = ax3.twinx()
        line4 = ax3_twin.plot(t, s["attitude_noise_deg"], label="姿态噪声", color="tab:gray", alpha=0.7, linewidth=1.0)
        ax3_twin.set_ylabel("噪声幅值（度）", color="tab:gray")
        ax3_twin.tick_params(axis='y', labelcolor='tab:gray')
        lines = line1 + line2 + line3 + line4
        labels = [line.get_label() for line in lines]
        ax3.legend(lines, labels, loc="upper right", frameon=False)

        ax4 = self.figure.add_subplot(224)
        ax4.set_title("4. 轨道衰减与目标测距面板")
        color1 = "tab:blue"
        ax4.set_xlabel("时间（秒）")
        ax4.set_ylabel("卫星高度（km）", color=color1)
        line1 = ax4.plot(t, s["sat_alt_km"], color=color1, label="卫星高度", linewidth=1.5)
        ax4.tick_params(axis='y', labelcolor=color1)

        ax4_twin = ax4.twinx()
        color2 = "tab:red"
        ax4_twin.set_ylabel("目标斜距（km）", color=color2)
        line2 = ax4_twin.plot(t, s["slant_range_km"], color=color2, linestyle="--", label="目标斜距", linewidth=1.5)
        ax4_twin.tick_params(axis='y', labelcolor=color2)
        
        lines = line1 + line2
        labels = [line.get_label() for line in lines]
        ax4.legend(lines, labels, loc="upper right", frameon=False)

        ax4.grid(True, alpha=0.3)

        self.figure.tight_layout(rect=[0, 0.03, 1, 0.94])

        # 保存当前数据用于 hover 交互
        self.current_time_data = t
        self.current_series_data = s
        # 明确划分主子图（用于显示文本）和所有用于绘制垂线的轴（包含 twin）
        self.main_axes = [ax1, ax2, ax3, ax4]
        self.vline_axes = [ax1, ax2, ax3, ax3_twin, ax4, ax4_twin]
        # 时间轴集合（仅在这些轴上响应 x=time 的 hover）
        self.time_axes = {ax2, ax3, ax3_twin, ax4, ax4_twin}

        self.canvas.draw()
        
        # 连接 hover 事件
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)
        
        self.export.setEnabled(True)

    def on_hover(self, event):
        """鼠标 hover 时显示对应时刻的详细数据"""
        # 清除之前的 hover 元素
        for artist in self.hover_artists:
            artist.remove()
        self.hover_artists.clear()
        
        if event.inaxes is None or not hasattr(self, 'current_time_data'):
            self.canvas.draw_idle()
            return

        # 如果在第一个子图（地图）上 hover，使用经纬度最近点查询显示位置相关信息
        try:
            map_ax = getattr(self, 'main_axes', [None])[0]
        except Exception:
            map_ax = None

        if event.inaxes == map_ax:
            # 地图交互：找到最近的卫星/切点点并标注
            s = self.current_series_data
            lon = event.xdata
            lat = event.ydata
            if lon is None or lat is None:
                self.canvas.draw_idle()
                return
            # 如果有切点数据，也计算切点最近索引，然后决定展示卫星还是切点信息
            sat_idx = None
            tang_idx = None
            sat_dist_sq = float('inf')
            tang_dist_sq = float('inf')

            if 'sat_lon' in s and 'sat_lat' in s and len(s.get('sat_lon', []))>0:
                lons = s['sat_lon']
                lats = s['sat_lat']
                sat_idx = min(range(len(lons)), key=lambda i: (lons[i]-lon)**2 + (lats[i]-lat)**2)
                sat_dist_sq = (lons[sat_idx]-lon)**2 + (lats[sat_idx]-lat)**2

            if 'tangent_lon' in s and 'tangent_lat' in s and len(s.get('tangent_lon', []))>0:
                tlons = s['tangent_lon']
                tlats = s['tangent_lat']
                tang_idx = min(range(len(tlons)), key=lambda i: (tlons[i]-lon)**2 + (tlats[i]-lat)**2)
                tang_dist_sq = (tlons[tang_idx]-lon)**2 + (tlats[tang_idx]-lat)**2

            # 阈值：若最近点距离超过阈值则不触发（防止在空白处误触发），阈值为 2 度
            threshold_sq = 4.0

            show_idx = None
            show_type = None
            if sat_idx is not None and sat_dist_sq <= tang_dist_sq and sat_dist_sq <= threshold_sq:
                show_idx = sat_idx
                show_type = 'sat'
            elif tang_idx is not None and tang_dist_sq < sat_dist_sq and tang_dist_sq <= threshold_sq:
                show_idx = tang_idx
                show_type = 'tang'

            if show_idx is None:
                # 未命中任何点
                self.canvas.draw_idle()
                return

            # 在地图上高亮该点
            try:
                if show_type == 'sat':
                    px = lons[show_idx]
                    py = lats[show_idx]
                    m = map_ax.scatter([px], [py], c='red', s=50, marker='o', zorder=10)
                else:
                    px = tlons[show_idx]
                    py = tlats[show_idx]
                    m = map_ax.scatter([px], [py], c='orange', s=50, marker='x', zorder=10)
                self.hover_artists.append(m)
            except Exception:
                pass

            # 同步到时间轴：绘制竖线并在其他子图显示分散信息（复用时间响应的逻辑）
            try:
                times = self.current_time_data
                idx = show_idx
                # 在所有用于竖线的轴上画竖线（包含 twin）
                for ax in getattr(self, 'vline_axes', [self.figure.axes[0], self.figure.axes[1], self.figure.axes[2], self.figure.axes[3]]):
                    try:
                        vline = ax.axvline(x=times[idx], color='red', linestyle='--', linewidth=1, alpha=0.5)
                        self.hover_artists.append(vline)
                    except Exception:
                        pass

                # 构建并显示与时间轴一致的分散信息框
                s = self.current_series_data
                t_val = times[idx]
                sat_state = "地影" if bool(s.get('sat_in_eclipse',[False])[idx]) else "日照"
                tang_state = "地影" if bool(s.get('tangent_in_eclipse',[False])[idx]) else "日照"

                info_sat = f"[卫星]\n时间: {t_val:.2f} 秒\n"
                info_sat += f"经度: {s.get('sat_lon',[0])[idx]:.3f}°\n"
                info_sat += f"纬度: {s.get('sat_lat',[0])[idx]:.3f}°\n"
                info_sat += f"高度: {s.get('sat_alt_km',[0])[idx]:.2f} km\n"
                info_sat += f"光照状态: {sat_state}\n"

                info_tang = f"[切点]\n时间: {t_val:.2f} 秒\n"
                info_tang += f"经度: {s.get('tangent_lon',[0])[idx]:.3f}°\n"
                info_tang += f"纬度: {s.get('tangent_lat',[0])[idx]:.3f}°\n"
                info_tang += f"高度: {s.get('tangent_alt_km',[0])[idx]:.2f} km\n"
                info_tang += f"光照状态: {tang_state}\n"

                info1 = f"时间: {t_val:.2f} 秒\n"
                if hasattr(self, 'fov_low') and idx < len(self.fov_low):
                    fov_min_val = self.fov_low[idx]
                    fov_max_val = self.fov_high[idx]
                else:
                    fov_min_val = s.get('fov_alt_min_km',[0])[idx]
                    fov_max_val = s.get('fov_alt_max_km',[0])[idx]
                info1 += f"视场最小高度: {fov_min_val:.2f} km\n"
                info1 += f"视场最大高度: {fov_max_val:.2f} km\n"
                info1 += f"切点高度: {s.get('tangent_alt_km',[0])[idx]:.2f} km\n"

                info2 = f"时间: {t_val:.2f} 秒\n"
                info2 += f"滚转角: {s.get('sat_roll_deg',[0])[idx]:.2f}°\n"
                info2 += f"俯仰角: {s.get('sat_pitch_deg',[0])[idx]:.2f}°\n"
                info2 += f"偏航角: {s.get('sat_yaw_deg',[0])[idx]:.2f}°\n"
                info2 += f"噪声: {s.get('attitude_noise_deg',[0])[idx]:.3f}°\n"

                info3 = f"时间: {t_val:.2f} 秒\n"
                info3 += f"卫星高度: {s.get('sat_alt_km',[0])[idx]:.2f} km\n"
                info3 += f"斜距: {s.get('slant_range_km',[0])[idx]:.2f} km\n"

                fp = FontProperties(family=['Microsoft YaHei', 'SimHei', 'DejaVu Sans'], size=7)
                bdict = dict(boxstyle='round', facecolor='#fffacd', alpha=0.9, pad=0.5)
                texts = []
                axes = getattr(self, 'main_axes', [])
                if len(axes) >= 1:
                    try:
                        t_top = axes[0].text(0.02, 0.98, info_tang, transform=axes[0].transAxes,
                                             fontproperties=fp, fontsize=7, verticalalignment='top', bbox=bdict)
                        texts.append(t_top)
                    except Exception:
                        pass
                    try:
                        t_bottom = axes[0].text(0.02, 0.02, info_sat, transform=axes[0].transAxes,
                                                fontproperties=fp, fontsize=7, verticalalignment='bottom', bbox=bdict)
                        texts.append(t_bottom)
                    except Exception:
                        pass
                for ax, txt in zip(axes[1:], [info1, info2, info3]):
                    try:
                        t = ax.text(0.02, 0.98, txt, transform=ax.transAxes,
                                    fontproperties=fp, fontsize=7, verticalalignment='top', bbox=bdict)
                        texts.append(t)
                    except Exception:
                        pass
                for tobj in texts:
                    self.hover_artists.append(tobj)
            except Exception:
                pass

            self.canvas.draw_idle()
            return

        # 仅在时间轴上响应（避免在地图轴上使用经度作为时间导致索引不对齐）
        if event.inaxes not in getattr(self, 'time_axes', set()):
            self.canvas.draw_idle()
            return

        # 获取鼠标位置对应的时间索引
        x_pos = event.xdata
        if x_pos is None:
            self.canvas.draw_idle()
            return
        
        # 找到最近的时间点
        times = self.current_time_data
        if len(times) == 0:
            self.canvas.draw_idle()
            return
        
        # 找最近的时间索引
        idx = min(range(len(times)), key=lambda i: abs(times[i] - x_pos))
        
        # 在所有用于竖线的轴上画竖线（包含 twin），以便视觉对齐
        for ax in getattr(self, 'vline_axes', [self.figure.axes[0], self.figure.axes[1], self.figure.axes[2], self.figure.axes[3]]):
            try:
                vline = ax.axvline(x=times[idx], color='red', linestyle='--', linewidth=1, alpha=0.5)
                self.hover_artists.append(vline)
            except Exception:
                pass
        
        # 构建详细信息并分散到对应子图（移除 emoji，避免字体问题）
        s = self.current_series_data
        t_val = times[idx]

        # 子图 0: 地图双信息框（左上切点，左下卫星）
        sat_state = "地影" if bool(s.get('sat_in_eclipse',[False])[idx]) else "日照"
        tang_state = "地影" if bool(s.get('tangent_in_eclipse',[False])[idx]) else "日照"

        info_sat = f"[卫星]\n时间: {t_val:.2f} 秒\n"
        info_sat += f"经度: {s.get('sat_lon',[0])[idx]:.3f}°\n"
        info_sat += f"纬度: {s.get('sat_lat',[0])[idx]:.3f}°\n"
        info_sat += f"高度: {s.get('sat_alt_km',[0])[idx]:.2f} km\n"
        info_sat += f"光照状态: {sat_state}\n"

        info_tang = f"[切点]\n时间: {t_val:.2f} 秒\n"
        info_tang += f"经度: {s.get('tangent_lon',[0])[idx]:.3f}°\n"
        info_tang += f"纬度: {s.get('tangent_lat',[0])[idx]:.3f}°\n"
        info_tang += f"高度: {s.get('tangent_alt_km',[0])[idx]:.2f} km\n"
        info_tang += f"光照状态: {tang_state}\n"

        # 子图 1: FOV / 靶心高度
        info1 = f"时间: {t_val:.2f} 秒\n"
        if hasattr(self, 'fov_low') and idx < len(self.fov_low):
            fov_min_val = self.fov_low[idx]
            fov_max_val = self.fov_high[idx]
        else:
            fov_min_val = s.get('fov_alt_min_km',[0])[idx]
            fov_max_val = s.get('fov_alt_max_km',[0])[idx]
        info1 += f"视场最小高度: {fov_min_val:.2f} km\n"
        info1 += f"视场最大高度: {fov_max_val:.2f} km\n"
        info1 += f"切点高度: {s.get('tangent_alt_km',[0])[idx]:.2f} km\n"

        # 子图 2: 姿态 / 噪声
        info2 = f"时间: {t_val:.2f} 秒\n"
        info2 += f"滚转角: {s.get('sat_roll_deg',[0])[idx]:.2f}°\n"
        info2 += f"俯仰角: {s.get('sat_pitch_deg',[0])[idx]:.2f}°\n"
        info2 += f"偏航角: {s.get('sat_yaw_deg',[0])[idx]:.2f}°\n"
        info2 += f"噪声: {s.get('attitude_noise_deg',[0])[idx]:.3f}°\n"

        # 子图 3: 轨道高度 / 斜距 曲线相关
        info3 = f"时间: {t_val:.2f} 秒\n"
        info3 += f"卫星高度: {s.get('sat_alt_km',[0])[idx]:.2f} km\n"
        info3 += f"斜距: {s.get('slant_range_km',[0])[idx]:.2f} km\n"

        # 在每个主子图分别显示信息框（避免在 twin 轴重复显示）
        fp = FontProperties(family=['Microsoft YaHei', 'SimHei', 'DejaVu Sans'], size=7)
        bdict = dict(boxstyle='round', facecolor='#fffacd', alpha=0.9, pad=0.5)
        texts = []
        axes = getattr(self, 'main_axes', [])
        if len(axes) >= 1:
            try:
                t_top = axes[0].text(0.02, 0.98, info_tang, transform=axes[0].transAxes,
                                     fontproperties=fp, fontsize=7, verticalalignment='top', bbox=bdict)
                texts.append(t_top)
            except Exception:
                pass
            try:
                t_bottom = axes[0].text(0.02, 0.02, info_sat, transform=axes[0].transAxes,
                                        fontproperties=fp, fontsize=7, verticalalignment='bottom', bbox=bdict)
                texts.append(t_bottom)
            except Exception:
                pass
        for ax, txt in zip(axes[1:], [info1, info2, info3]):
            try:
                t = ax.text(0.02, 0.98, txt, transform=ax.transAxes,
                            fontproperties=fp, fontsize=7, verticalalignment='top', bbox=bdict)
                texts.append(t)
            except Exception:
                pass

        for tobj in texts:
            self.hover_artists.append(tobj)
        
        # 刷新画布
        self.canvas.draw_idle()

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出", "", "*.csv")
        if path:
            export_job_data(self.current_job_id, path, "csv")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei"))
    w = AtmosOrbitApp()
    w.show()
    sys.exit(app.exec_())