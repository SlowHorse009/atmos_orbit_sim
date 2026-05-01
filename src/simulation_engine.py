import os
import math
import json
import pandas as pd
from pathlib import Path
import orekit
from org.orekit.data import DataProvidersManager, ZipJarCrawler # type: ignore
from java.io import File # type: ignore

# 导入核心模块
from org.orekit.utils import Constants # type: ignore
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore
from org.orekit.bodies import GeodeticPoint # type: ignore
from .orekit_generator import OrekitOrbitGenerator
from .geodesy_engine import WGS84GeodesyEngine
from .attitude_control import DynamicAttitudeController
from .sensor_optics import LimbOpticsSimulator
from orekit.pyhelpers import setup_orekit_curdir

class SimulationEngine:
    def __init__(self):
        """
        初始化仿真引擎 (懒加载 JVM 与数据路径对齐)
        """
        self.project_root = Path(__file__).resolve().parent.parent
        self.data_path = self.project_root / 'data' / 'orekit-data.zip'
        self.output_dir = self.project_root / 'output'
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 安全启动 JVM (防崩溃锁)
        self._ensure_jvm_started()
        
        # 2. 装载核心系统
        self.geodesy_sys = WGS84GeodesyEngine()
        self.attitude_sys = DynamicAttitudeController()
        self.optics_sys = LimbOpticsSimulator(focal_length_mm=850.0, sensor_size_mm=32.5)
        
    def _ensure_jvm_started(self):
        """线程安全的 JVM 启动器与全局数据装载"""
        try:
            vm_env = orekit.getVMEnv()
            if vm_env is None:
                orekit.initVM()
                print("☕ JVM 引擎已成功启动。")
                
                # --- 检查本地路径，避免越权下载 ---
                if not self.data_path.exists():
                    raise FileNotFoundError(
                        f"\n错误：找不到核心物理数据文件！\n"
                        f"期望路径: {self.data_path}\n"
                        f"请手动将 orekit-data.zip 放入上述目录。"
                    )
                # 使用官方 wrapper 挂载数据，完美将数据注入底层 DataContext
                setup_orekit_curdir(str(self.data_path))
                print(f"成功挂载本地物理数据: {self.data_path.name}")
                
        except Exception as e:
            # 捕获已经启动的报错
            pass

    def run_task(self, config_json_path):
        """
        [对外核心接口] 前端/外部调用此方法执行全链路推演
        """
        # 1. 解析前端传来的 JSON 配置
        with open(config_json_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            
        target_alt_m = cfg['payload']['target_alt_m']
        enable_noise = cfg['environment']['enable_noise']
        duration = cfg['simulation']['duration_sec']
        step = cfg['simulation']['step_sec']
        
        # 2. 动态生成轨道 (这里将 JSON 里的轨道参数传给发生器)
        orbit_sys = OrekitOrbitGenerator(
            prop_model=cfg['orbit']['type'],
            a=cfg['orbit']['keplerian']['a'],
            e=cfg['orbit']['keplerian']['e'],
            i=cfg['orbit']['keplerian']['i'],
            raan=cfg['orbit']['keplerian']['raan'],
            arg_pe=cfg['orbit']['keplerian']['arg_pe'],
            m0=cfg['orbit']['keplerian']['m0']
        )
        df_ephem = orbit_sys.generate_ephemeris_dataframe(duration, step)
        
        # 3. 执行推演主循环 (收集数据)
        result_records = []
        for index, row in df_ephem.iterrows():
            t = row['time_sec']
            date = orbit_sys.initial_date.shiftedBy(float(t))
            
            # 获取卫星当前状态
            x, y, z = row['x'], row['y'], row['z']
            vx, vy, vz = row['vx'], row['vy'], row['vz']
            
            # --- [核心控制] 高精度 WGS84 补偿与噪声注入 ---
            pitch, actual_los, noise = self.attitude_sys.get_pointing_command(
                x, y, z, vx, vy, vz, target_alt_m, self.geodesy_sys, self.optics_sys, date,
                enable_noise=enable_noise, t_sec=t
            )
            
            # --- [光学几何] 构建局部轨道坐标系并生成最终视线向量 ---
            pos_ecef = Vector3D(float(x), float(y), float(z))
            vel_ecef = Vector3D(float(vx), float(vy), float(vz))
            x_dir, _, z_dir = self.optics_sys._build_local_orbital_frame(pos_ecef, vel_ecef)
            
            # 这是相机的硬件表观指向 (大脑输出的指令)
            los_cmd = self.optics_sys._get_los_vector(x_dir, z_dir, actual_los)
            
            # ==========================================
            # [V2.0 环境物理真值] 宇宙引擎重现光行差与地球自转！
            # ==========================================
            earth_omega = Vector3D(0.0, 0.0, Constants.WGS84_EARTH_ANGULAR_VELOCITY)
            vel_absolute_in_ecef = vel_ecef.add(Vector3D.crossProduct(earth_omega, pos_ecef))
            
            # 宇宙引擎计算进入镜头的真实物理光子路径
            los_physical = self.optics_sys.apply_velocity_aberration(los_cmd, vel_absolute_in_ecef)
            
            # --- [大地测量] 靶心切点寻优 (必须用物理光线去求交！) ---
            tgt_lat, tgt_lon, tgt_alt_m_actual = self.geodesy_sys.get_limb_tangent_lla(
                x, y, z, los_physical.getX(), los_physical.getY(), los_physical.getZ(), date
            )
            
            # --- [环境探测] 卫星与切点的日照/阴影状态 ---
            sat_eclipse = self.geodesy_sys.is_in_eclipse(x, y, z, date)
            tgt_gp = GeodeticPoint(math.radians(tgt_lat), math.radians(tgt_lon), float(tgt_alt_m_actual))
            tgt_ecef = self.geodesy_sys.earth.transform(tgt_gp)
            tgt_eclipse = self.geodesy_sys.is_in_eclipse(tgt_ecef.getX(), tgt_ecef.getY(), tgt_ecef.getZ(), date)
            
            # --- 数据打点 ---
            result_records.append({
                'T_sec': t,
                'Sat_X_m': x, 'Sat_Y_m': y, 'Sat_Z_m': z,
                'Cmd_Pitch_deg': pitch,
                'Actual_LOS_deg': actual_los,
                'Noise_deg': noise,
                'Tgt_Lat_deg': tgt_lat,
                'Tgt_Lon_deg': tgt_lon,
                'Tgt_Alt_km': tgt_alt_m_actual / 1000.0,
                'Illum_Sat': 'ECLP' if sat_eclipse else 'SUN',
                'Illum_Tgt': 'ECLP' if tgt_eclipse else 'SUN'
            })
            
        # 4. 高速持久化存储：导出为 Parquet
        df_result = pd.DataFrame(result_records)
        output_filename = f"sim_result_tgt{int(target_alt_m/1000)}km.parquet"
        output_filepath = self.output_dir / output_filename
        
        # 引擎要求安装 pyarrow 或 fastparquet
        df_result.to_parquet(str(output_filepath), engine='pyarrow', compression='snappy')
        
        print(f"✅ 任务完成！高速数据已导出至: {output_filepath}")
        
        # 返回文件绝对路径给前端，前端去读这个文件就行了
        return str(output_filepath)