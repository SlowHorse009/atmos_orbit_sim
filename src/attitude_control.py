import math
import numpy as np

# 引入 3D 向量库，统一数据结构
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore

class DynamicAttitudeController:
    """
    通用型动态姿态与抖动控制器 (WGS84 动态向径升级版)
    彻底解耦业务逻辑与硬件安装，并接入真实地球曲率感知
    """
    def __init__(self, 
                 mount_pitch_deg=0.0, 
                 mount_roll_deg=0.0,
                 mount_yaw_deg=0.0,
                 drift_rate_arcsec_s=0.01,
                 jitter_3sigma_arcsec=1.5):
        """
        :param mount_pitch_deg: [硬件预留入口] 相机入瞳光轴相对于卫星本体的安装俯仰角
        :param drift_rate_arcsec_s: 低频热漂移率 (角秒/秒)
        :param jitter_3sigma_arcsec: 高频微振动 3sigma 极值 (角秒)
        """
        self.mount_pitch = mount_pitch_deg
        self.mount_roll = mount_roll_deg
        self.mount_yaw = mount_yaw_deg
        
        self.drift_rate_deg = drift_rate_arcsec_s / 3600.0
        self.jitter_1sigma_deg = (jitter_3sigma_arcsec / 3600.0) / 3.0

    def calc_ideal_nadir_angle(self, sat_pos_ecef, target_alt_m, geodesy_engine, date):
        """
        [升维核心] 结合 WGS84 椭球几何，计算理想视线地心角
        """
        if np.isnan(target_alt_m):
            return np.nan
            
        # 1. 获取卫星在当前位置的绝对地心距离
        r_sat = sat_pos_ecef.getNorm()
        
        # 2. 召唤 WGS84 引擎，获取当前精确经纬度
        lat, lon, _ = geodesy_engine.get_sat_lla(
            sat_pos_ecef.getX(), sat_pos_ecef.getY(), sat_pos_ecef.getZ(), date
        )
        
        # 3. 计算卫星当前纬度下，真实的地球向径 (Geocentric Radius)
        # 抛弃死板的 6378137，地球极半径和赤道半径相差 21km，必须用椭球公式动态算
        a = geodesy_engine.earth.getEquatorialRadius()
        f = geodesy_engine.earth.getFlattening()
        e2 = 2 * f - f**2
        
        lat_rad = math.radians(lat)
        sin_lat = math.sin(lat_rad)
        
        # WGS84 局部地球半径解析式
        r_earth_local = a * math.sqrt(1 - e2 * sin_lat**2)
        
        # 4. 基于局部真实半径，解算姿态指令角
        # sin(theta) = (局部地球半径 + 目标切点高度) / 卫星地心向径
        ratio = (r_earth_local + target_alt_m) / r_sat
        ratio = np.clip(ratio, -1.0, 1.0)
        
        return math.degrees(math.asin(ratio))

    def get_pointing_command(self, x, y, z, target_alt_m, exposure_time_sec, geodesy_engine, date):
        """
        输入当前三维坐标和目标，输出系统指令
        
        :param x, y, z: 卫星当前 ECEF 坐标
        :param target_alt_m: 客户随时指定的观测高度 (米)
        :param exposure_time_sec: 曝光持续时间
        :param geodesy_engine: 大地测量解析引擎实例
        :param date: 当前绝对时间
        :return: (卫星本体俯仰指令角, 镜子抖动误差, 绝对视轴偏角)
        """
        sat_pos_ecef = Vector3D(float(x), float(y), float(z))
        
        # 1. 算理论视线 (具备局部地球曲率感知能力)
        nadir_angle_deg = self.calc_ideal_nadir_angle(sat_pos_ecef, target_alt_m, geodesy_engine, date)
        
        # 2. 扣除相机自身安装的固定偏角
        sat_body_pitch_deg = nadir_angle_deg - self.mount_pitch
        
        # 3. 注入高频物理微振动与低频漂移
        drift_error = self.drift_rate_deg * exposure_time_sec
        high_freq_error = np.random.normal(0.0, self.jitter_1sigma_deg)
        total_jitter_deg = drift_error + high_freq_error
        
        return sat_body_pitch_deg, total_jitter_deg, nadir_angle_deg