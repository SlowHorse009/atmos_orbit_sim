import math
import numpy as np
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore

class DynamicAttitudeController:
    """
    临边探测卫星动态姿态控制器
    支持 WGS84 椭球体高精度高度跟踪、载荷死锁模式以及多频段物理扰动注入。
    """

    def __init__(self, mount_pitch_deg=68.0, drift_rate_arcsec_s=0.05, 
                 jitter_3sigma_arcsec=1.5, orbital_period_sec=5400.0):
        """
        初始化控制器参数
        
        :param mount_pitch_deg: 载荷相机在卫星本体上的安装偏角 (度)
        :param drift_rate_arcsec_s: 低频热漂移率 (角秒/秒)
        :param jitter_3sigma_arcsec: 高频微振动 3-sigma 阈值 (角秒)
        :param orbital_period_sec: 标称轨道周期，用于热漂移正弦建模 (秒)
        """
        self.mount_pitch = mount_pitch_deg
        # 单位转换：将角秒转换为度
        self.drift_rate_deg = drift_rate_arcsec_s / 3600.0
        self.jitter_1sigma_deg = (jitter_3sigma_arcsec / 3.0) / 3600.0
        self.orbital_period_sec = orbital_period_sec

    def calc_ideal_nadir_angle(self, pos_ecef, target_alt_m, geodesy_engine, date):
        """
        [核心几何引擎] 严密 WGS84 椭球体下俯角定点迭代求解器 (0.9km 精度版)
        
        :param pos_ecef: 卫星当前 ECEF 坐标向量 (Vector3D)
        :param target_alt_m: 目标观测切点高度 (米)
        :param geodesy_engine: WGS84 大地测量引擎实例
        :param date: 当前绝对时间 (AbsoluteDate)
        :return: 补偿地球曲率后的理论绝对视轴下俯角 (度)
        """
        # 1. 获取卫星当前的精确三维地心距离 (绝对模长)
        d_sat = pos_ecef.getNorm() 
        
        # 2. 获取卫星当前的地理纬度 (用于初始化切点纬度猜测)
        sat_lat, _, _ = geodesy_engine.get_sat_lla(
            pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(), date
        )
        
        a = geodesy_engine.earth.getEquatorialRadius()
        f = geodesy_engine.earth.getFlattening()
        b = a * (1.0 - f)
        
        # 初始猜测：假设切点半径等于赤道半径
        current_r_tgt = a  
        ideal_nadir_rad = 0.0
        
        # 3. 高精度定点迭代 (5次即可消除 99% 的椭球体偏离误差)
        for _ in range(5):
            # 核心几何公式：sin(下俯角) = (切点半径 + 目标高度) / 卫星地心距离
            val = (current_r_tgt + target_alt_m) / d_sat
            val = max(0.0, min(1.0, val)) # 边界安全检查
            
            ideal_nadir_rad = math.asin(val)
            
            # 估算切点纬度以更新局部曲率半径
            central_angle_rad = math.pi / 2.0 - ideal_nadir_rad
            approx_tgt_lat = math.radians(sat_lat) + central_angle_rad
            
            # WGS84 椭球半径计算公式
            sin_lat = math.sin(approx_tgt_lat)
            cos_lat = math.cos(approx_tgt_lat)
            current_r_tgt = math.sqrt(
                ((a**2 * cos_lat)**2 + (b**2 * sin_lat)**2) /
                ((a * cos_lat)**2 + (b * sin_lat)**2)
            )

        return math.degrees(ideal_nadir_rad)

    def _generate_noise_model(self, t_sec, is_thrusting):
        """
        [内部私有方法] 生成高保真多频段物理扰动
        
        :param t_sec: 当前飞行相对时间 (秒)，用于解算低频相位
        :param is_thrusting: 推力器状态标志位，开启则注入大幅度耦合噪声
        :return: 综合扰动角 (度)
        """
        # 1. 低频热漂移：模拟星箭结构随轨道周期的热形变误差 (正弦波模型)
        max_drift_amp = self.drift_rate_deg * (self.orbital_period_sec / 4.0) 
        thermal_drift = max_drift_amp * math.sin(2 * math.pi * t_sec / self.orbital_period_sec)
        
        # 2. 高频微振动：模拟飞轮、制冷机等旋转部件引起的高频抖动 (高斯白噪声)
        high_freq_jitter = np.random.normal(0.0, self.jitter_1sigma_deg)
        
        # 3. 轨控耦合：推力器开启时的阶跃偏置与振动放大
        thrust_offset = 0.005 if is_thrusting else 0.0
        noise_gain = 3.0 if is_thrusting else 1.0

        return thermal_drift + (high_freq_jitter * noise_gain) + thrust_offset

    def get_pointing_command(self, x, y, z, target_alt_m, geodesy_engine, date, 
                             enable_noise=False, t_sec=0.0, is_thrusting=False):
        """
        [接口] 动态补偿模式：计算用于实时跟踪目标的系统指令
        
        :param x, y, z: 卫星当前 ECEF 坐标 (米)
        :param target_alt_m: 目标观测高度 (米)
        :param geodesy_engine: 大地测量解析引擎实例
        :param date: 当前绝对时间
        :param enable_noise: 是否注入物理扰动 (默认关闭)
        :param t_sec: 飞行时间，用于噪声相位解算
        :param is_thrusting: 动力学库是否正在执行推力机动
        :return: (本体俯仰指令角, 绝对视线角, 注入的噪声分量)
        """
        pos_ecef = Vector3D(float(x), float(y), float(z))
        
        # 1. 纯几何计算
        nadir_angle_deg = self.calc_ideal_nadir_angle(pos_ecef, target_alt_m, geodesy_engine, date)
        sat_body_pitch_deg = nadir_angle_deg - self.mount_pitch
        
        # 2. 噪声注入
        noise_comp = self._generate_noise_model(t_sec, is_thrusting) if enable_noise else 0.0
        actual_los = nadir_angle_deg + noise_comp
        
        return sat_body_pitch_deg, actual_los, noise_comp

    def get_locked_pointing_command(self, locked_nadir_angle_deg, 
                                    enable_noise=False, t_sec=0.0, is_thrusting=False):
        """
        [接口] 载荷锁死模式：计算固定视角下的系统指令 (支持噪声评估)
        
        :param locked_nadir_angle_deg: 初始时刻锁定的固定下俯角 (度)
        :param enable_noise: 是否注入物理扰动 (默认关闭)
        :param t_sec: 飞行时间，用于噪声相位解算
        :param is_thrusting: 动力学库是否正在执行推力机动
        :return: (本体固定指令角, 实际偏离后的视线角, 注入的噪声分量)
        """
        sat_body_pitch_deg = locked_nadir_angle_deg - self.mount_pitch
        
        # 噪声注入
        noise_comp = self._generate_noise_model(t_sec, is_thrusting) if enable_noise else 0.0
        actual_los = locked_nadir_angle_deg + noise_comp
        
        return sat_body_pitch_deg, actual_los, noise_comp