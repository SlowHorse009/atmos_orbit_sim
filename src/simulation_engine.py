import os
import json
import math
import pandas as pd
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore
from org.orekit.utils import Constants # type: ignore

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # src 目录
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)              # atmos_orbit_sim 根目录

from .orekit_generator import OrekitOrbitGenerator
from .optics_simulator import LimbOpticsSimulator
from .attitude_controller import DynamicAttitudeController
from .geodesy_engine import WGS84GeodesyEngine

class SimulationEngine:
    """
    临边探测高保真仿真引擎
    """
    def __init__(self, config_path_or_dict):
        """
        :param config_path_or_dict: 可以是 JSON 文件的绝对路径，也可以是前端直接传过来的 Python 字典
        """
        # 1. 解析配置输入
        if isinstance(config_path_or_dict, str):
            with open(config_path_or_dict, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = config_path_or_dict

        print("[引擎启动] 正在解析配置协议并初始化底层物理模型...")

        # 2. 实例化大地测量引擎
        self.geodesy_sys = WGS84GeodesyEngine()

        # 3. 实例化光学载荷模拟器 
        optics_cfg = self.config["payload_optics"]
        mount_cfg = optics_cfg.get("mounting_angles", {})
        self.optics_sys = LimbOpticsSimulator(
            fov_deg=optics_cfg.get("fov_deg"),
            focal_length_mm=optics_cfg.get("focal_length_mm"),
            sensor_size_mm=optics_cfg.get("sensor_size_mm"),
            mount_roll_deg=mount_cfg.get("mount_roll_deg", 68.0),
            mount_pitch_deg=mount_cfg.get("mount_pitch_deg", 0.0),
            mount_yaw_deg=mount_cfg.get("mount_yaw_deg", 0.0)
        )

        # 4. 推导轨道周期
        orb_cfg = self.config["orbit_propagation"]
        sat_a = orb_cfg.get("a", 6878137.0)  # 获取半长轴 (米)
        mu_earth = Constants.WGS84_EARTH_MU  # 调取 Orekit 底层的地球引力常数

        # 开普勒第三定律：T = 2 * pi * sqrt(a^3 / mu)
        adaptive_orbital_period = 2.0 * math.pi * math.sqrt((sat_a ** 3) / mu_earth)
        print(f"[物理引擎] 已根据半长轴 {sat_a/1000}km 自适应推导出轨道周期: {adaptive_orbital_period:.2f} 秒")

        # 5. 实例化姿态控制状态机
        att_cfg = self.config["attitude_control"]
        pert_cfg = att_cfg.get("perturbations", {})
        self.attitude_sys = DynamicAttitudeController(
            mode=att_cfg.get("mode", "DYNAMIC"),
            target_alt_km=att_cfg.get("target_alt_km"),
            locked_angle_deg=att_cfg.get("locked_angle_deg"),
            enable_noise=pert_cfg.get("enable_noise", False),
            drift_rate_arcsec_s=pert_cfg.get("drift_rate_arcsec_s", 0.05),
            jitter_3sigma_arcsec=pert_cfg.get("jitter_3sigma_arcsec", 1.5),
            orbital_period_sec=adaptive_orbital_period
        )

        # 5. 实例化轨道动力学生成器
        orb_cfg = self.config["orbit_propagation"]
        force_cfg = orb_cfg.get("perturbations", {})
        self.orbit_sys = OrekitOrbitGenerator(
            prop_model=orb_cfg.get("model", "HPOP"),
            epoch_iso=orb_cfg.get("epoch_iso"),
            a=orb_cfg.get("a"), e=orb_cfg.get("e"), i=orb_cfg.get("i"),
            raan=orb_cfg.get("raan"), arg_pe=orb_cfg.get("arg_pe"), m0=orb_cfg.get("m0"),
            tle_line1=orb_cfg.get("tle_line1"), tle_line2=orb_cfg.get("tle_line2"),
            mass_kg=orb_cfg.get("mass_kg", 1000.0),
            cross_section_m2=orb_cfg.get("cross_section_m2", 5.0),
            cd=orb_cfg.get("cd", 2.2), cr=orb_cfg.get("cr", 1.2),
            gravity_degree=force_cfg.get("gravity_degree", 6),
            gravity_order=force_cfg.get("gravity_order", 6),
            enable_thirdbody=force_cfg.get("enable_thirdbody", True),
            enable_drag=force_cfg.get("enable_drag", False),
            enable_srp=force_cfg.get("enable_srp", False)
        )

        self.duration = orb_cfg.get("duration_sec", 5400.0)
        self.step = orb_cfg.get("step_sec", 1.0)

        # 基于项目绝对根目录创建 output！
        self.output_dir = os.path.join(PROJECT_ROOT, "output")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"[系统] 已在根目录创建数据落盘文件夹: {self.output_dir}")

        print(f"[引擎配置] 仿真总时长设定为: {self.duration} 秒")
        print("[引擎就绪] 物理模型初始化完毕。")

    def run_simulation(self, auto_export=True, output_filename="limb_sim_results.parquet"):
        """
        执行主推演循环，生成并缓存全量遥测数据
        """
        print(f"正在推演 {self.duration} 秒轨道数据...")
        orbit_df = self.orbit_sys.generate_ephemeris_dataframe(self.duration, self.step)
        
        results = []
        total_steps = len(orbit_df)
        print("正在执行光电几何映射与靶心求交计算...")
        
        for index, row in orbit_df.iterrows():
            t = row['time_sec']
            x, y, z = row['x'], row['y'], row['z']
            vx, vy, vz = row['vx'], row['vy'], row['vz']
            
            current_date = self.orbit_sys.initial_date.shiftedBy(float(t))
            
            # --- 大地测量与状态解算 ---
            sat_lat, sat_lon, sat_alt = self.geodesy_sys.get_sat_lla(x, y, z, current_date)
            
            sat_roll, sat_pitch, sat_yaw, noise = self.attitude_sys.get_attitude_command(
                x, y, z, vx, vy, vz, self.geodesy_sys, self.optics_sys, current_date, t_sec=t
            )
            
            # --- 光学映射与求交 ---
            pos_v = Vector3D(float(x), float(y), float(z))
            vel_v = Vector3D(float(vx), float(vy), float(vz))
            x_dir, y_dir, z_dir = self.optics_sys._build_local_orbital_frame(pos_v, vel_v)
            
            los_cmd_ecef = self.optics_sys._get_true_los_vector(
                x_dir, y_dir, z_dir, 
                math.radians(sat_roll), 
                math.radians(sat_pitch), 
                math.radians(sat_yaw)
            )
            
            earth_omega = Vector3D(0.0, 0.0, Constants.WGS84_EARTH_ANGULAR_VELOCITY)
            vel_absolute = vel_v.add(Vector3D.crossProduct(earth_omega, pos_v))
            los_physical = self.optics_sys.apply_velocity_aberration(los_cmd_ecef, vel_absolute)
            
            t_lat, t_lon, t_alt, slant_range_m = self.geodesy_sys.get_limb_tangent_lla_brent(
                x, y, z, los_physical.getX(), los_physical.getY(), los_physical.getZ(), current_date
            )
            
            in_eclipse = self.geodesy_sys.is_in_eclipse(
                pos_v.getX(), pos_v.getY(), pos_v.getZ(), current_date
            )
            
            alt_min, alt_max = self.optics_sys.calculate_altitude_range(
                x, y, z, vx, vy, vz, sat_roll, sat_pitch, sat_yaw, self.geodesy_sys, current_date
            )
            
            results.append({
                "time_sec": t,
                "sat_x": x, "sat_y": y, "sat_z": z,
                "sat_lat": sat_lat, "sat_lon": sat_lon, "sat_alt_km": sat_alt / 1000.0,
                "sat_roll_deg": sat_roll,
                "sat_pitch_deg": sat_pitch,
                "sat_yaw_deg": sat_yaw,
                "attitude_noise_deg": noise,
                "tangent_lat": t_lat,
                "tangent_lon": t_lon,
                "tangent_alt_km": t_alt / 1000.0,
                "slant_range_km": slant_range_m / 1000.0,
                "fov_alt_min_km": alt_min / 1000.0,
                "fov_alt_max_km": alt_max / 1000.0,
                "in_eclipse": in_eclipse
            })
            
            if index > 0 and index % 1000 == 0:
                print(f"   进度: {index}/{total_steps} 帧计算完成...")

        print("仿真推演全部完成！")
        
        # 将结果存为实例属性，方便后续灵活调用
        self.df_results = pd.DataFrame(results)
        if auto_export:
            self.export_analysis_report(output_filename)
            
        return self.df_results

    def export_analysis_report(self, filename="limb_sim_results.parquet"):
        """
        将仿真数据导出到 output 文件夹，并生成快速统计摘要
        """
        if not hasattr(self, 'df_results') or self.df_results is None:
            raise RuntimeError("请先执行 run_simulation() 生成数据！")

        # 拼接安全的输出路径
        output_path = os.path.join(self.output_dir, filename)

        self.df_results.to_parquet(output_path, engine='pyarrow', index=False)
        
        # 生成数据概览与物理验证
        print("\n" + "="*50)
        print("临边探测高保真仿真统计摘要")
        print("="*50)
        print(f"数据已极速压缩并落盘至: {output_path}")
        print(f"总计推演帧数: {len(self.df_results)}")
        
        # 统计核心指标
        alt_mean = self.df_results['tangent_alt_km'].mean()
        alt_std = self.df_results['tangent_alt_km'].std()
        print(f"目标切点高度控制: {alt_mean:.4f} km (1σ: {alt_std:.6f} km)")
        
        slant_min = self.df_results['slant_range_km'].min()
        slant_max = self.df_results['slant_range_km'].max()
        print(f"绝对斜距变化范围: {slant_min:.2f} ~ {slant_max:.2f} km")

        # 统计视场深空现象
        nan_count = self.df_results['fov_alt_max_km'].isna().sum()
        if nan_count > 0:
            percentage = (nan_count / len(self.df_results)) * 100
            print(f"视场上边缘切入深空: {nan_count} 帧 ({percentage:.1f}%) -> 物理现象合理")
        print("="*50 + "\n")