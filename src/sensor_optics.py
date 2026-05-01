import math
import numpy as np

# 引入强大的 Java 底层 3D 向量库
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore

class LimbOpticsSimulator:
    """
    高保真临边观测光学映射解析器 (WGS84 椭球体严密版)
    负责将相机的物理参数、卫星轨道矢量与三维姿态结合，解算出大气层的实际探测切点范围
    """
    def __init__(self, fov_deg=None, focal_length_mm=None, sensor_size_mm=32.5):
        """
        灵活初始化接口 (支持几何 FOV 驱动 或 硬件参数驱动)
        """
        if fov_deg is not None:
            self.fov_deg = float(fov_deg)
            self.fov_rad = math.radians(self.fov_deg)
        elif focal_length_mm is not None:
            self.f_mm = float(focal_length_mm)
            self.sensor_size_mm = float(sensor_size_mm)
            # FOV = 2 * arctan( d / (2 * f) )
            self.fov_rad = 2.0 * math.atan(self.sensor_size_mm / (2.0 * self.f_mm))
            self.fov_deg = math.degrees(self.fov_rad)
        else:
            raise ValueError("初始化失败：必须提供 [fov_deg] 或 [focal_length_mm] 中的至少一项！")

    def _build_local_orbital_frame(self, pos_ecef, vel_ecef):
        """
        构建局部轨道坐标系 (LVLH) 
        使用手动归一化规避 JCC 桥接 Bug
        """
        # Z轴 (天底方向 Nadir)：指向地心
        z_vec = pos_ecef.scalarMultiply(-1.0)
        z_dir = z_vec.scalarMultiply(1.0 / z_vec.getNorm())
        
        # Y轴 (轨道法向 Cross-track)：位置与速度的叉乘
        y_vec = pos_ecef.crossProduct(vel_ecef)
        y_dir = y_vec.scalarMultiply(1.0 / y_vec.getNorm())
        
        # X轴 (飞行方向 Along-track)：完成右手系
        x_vec = y_dir.crossProduct(z_dir)
        x_dir = x_vec.scalarMultiply(1.0 / x_vec.getNorm())
        
        return x_dir, y_dir, z_dir

    def _get_los_vector(self, x_dir, z_dir, pitch_deg):
        """生成空间中的视线方向矢量 (LOS)"""
        pitch_rad = math.radians(pitch_deg)
        
        term_z = z_dir.scalarMultiply(math.cos(pitch_rad))
        term_x = x_dir.scalarMultiply(math.sin(pitch_rad))
        
        los_vec = term_z.add(term_x)
        # 手动归一化
        los_dir = los_vec.scalarMultiply(1.0 / los_vec.getNorm())
        return los_dir

    def calculate_altitude_range(self, x, y, z, vx, vy, vz, absolute_los_deg, geodesy_engine, date):
        """
        [升维核心] 根据当前卫星的三维状态和视场，通过射线与椭球体求交，算出最严密的探测范围
        
        :param x, y, z: 卫星 ECEF 位置 (米)
        :param vx, vy, vz: 卫星 ECEF 速度 (米/秒)
        :param absolute_los_deg: 视场中心的绝对下俯角 (度)
        :param geodesy_engine: 传入实例化的 WGS84GeodesyEngine
        :param date: 绝对时间 AbsoluteDate
        :return: (最低切点高度, 最高切点高度) 米，如果看向太空则返回 NaN
        """
        pos_ecef = Vector3D(float(x), float(y), float(z))
        vel_ecef = Vector3D(float(vx), float(vy), float(vz))
        
        # 1. 建立卫星的局部三维空间基底
        x_dir, _, z_dir = self._build_local_orbital_frame(pos_ecef, vel_ecef)
        
        # 2. 算视场的上下边缘绝对角度 (成倒立像，角度加半个FOV是看向更低)
        los_bottom_deg = absolute_los_deg + (self.fov_deg / 2.0)
        los_top_deg = absolute_los_deg - (self.fov_deg / 2.0)
        
        # 3. 将标量角度转化为 3D 绝对空间中的 LOS 视线矢量
        los_vec_bottom = self._get_los_vector(x_dir, z_dir, los_bottom_deg)
        los_vec_top = self._get_los_vector(x_dir, z_dir, los_top_deg)
        
        # 4. 召唤 WGS84 引擎，执行最硬核的 3D 射线椭球求交
        _, _, alt_min = geodesy_engine.get_limb_tangent_lla(
            pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
            los_vec_bottom.getX(), los_vec_bottom.getY(), los_vec_bottom.getZ(),
            date
        )
        
        _, _, alt_max = geodesy_engine.get_limb_tangent_lla(
            pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
            los_vec_top.getX(), los_vec_top.getY(), los_vec_top.getZ(),
            date
        )
        
        return alt_min, alt_max
    
    def apply_velocity_aberration(self, los_cmd_ecef, vel_ecef):
        """
        [新增物理模型] 一阶相对论光行差补偿 (Velocity Aberration)
        
        物理背景：卫星以约 7.5km/s 的速度飞行，光子抵达探测器的这段时间里，卫星已发生位移。
        为了捕捉特定方向的光子，硬件镜头必须“提前”偏转一个微小角度。
        
        :param los_cmd_ecef: 硬件相机的表观指令视线 (Apparent LOS)
        :param vel_ecef: 卫星当前绝对速度向量 (m/s)
        :return: 补偿后的真实物理光线空间路径 (True LOS)
        """
        from org.orekit.utils import Constants # type: ignore
        from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore
        
        # 提取真空中光速 (约 2.9979 x 10^8 m/s)
        c = Constants.SPEED_OF_LIGHT
        
        # 计算光行差微扰向量: v/c
        v_over_c = Vector3D(1.0 / c, vel_ecef)
        
        # 几何反演：镜头指向 los_cmd，意味着接收到的光子其实来自 los_cmd - v/c 的方向
        # 1. 先做减法，得到未归一化的偏移向量
        los_physical_unnorm = los_cmd_ecef.subtract(v_over_c)
        
        # 2. 提取向量模长
        norm = los_physical_unnorm.getNorm()
        
        # 3. 手动执行标量乘法实现归一化 (向量 * 1/模长)
        los_physical = los_physical_unnorm.scalarMultiply(1.0 / norm)
        
        return los_physical
    