import math
import numpy as np
from scipy.optimize import minimize_scalar

# 导入 Orekit 相关的几何与地球模型类
from org.orekit.models.earth import ReferenceEllipsoid # type: ignore
from org.orekit.frames import FramesFactory # type: ignore
from org.orekit.utils import IERSConventions # type: ignore
from org.hipparchus.geometry.euclidean.threed import Vector3D, Line # type: ignore
from org.orekit.bodies import CelestialBodyFactory # type: ignore

class WGS84GeodesyEngine:
    """
    基于 Orekit 的工业级 WGS84 空间几何解析引擎
    专解 ECEF坐标 与 椭球体经纬度 的高精度转换，及临边切点寻优
    """
    def __init__(self):
        # 获取包含 IERS 2010 极移和地球自转的 ITRF 地固系
        self.ecef_frame = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
        
        # 实例化极其严密的 WGS84 标准参考椭球体
        self.earth = ReferenceEllipsoid.getWgs84(self.ecef_frame)

        # 获取太阳天体对象
        self.sun = CelestialBodyFactory.getSun()

    def get_sat_lla(self, x, y, z, date):
        """
        严密解算卫星本体的 经度(度), 纬度(度), 高度(米)
        """
        pos_ecef = Vector3D(float(x), float(y), float(z))
        
        # 直接调用 Orekit 底层的 WGS84 转换器
        geodetic_pt = self.earth.transform(pos_ecef, self.ecef_frame, date)
        
        lat = math.degrees(geodetic_pt.getLatitude())
        lon = math.degrees(geodetic_pt.getLongitude())
        alt = geodetic_pt.getAltitude()
        
        return lat, lon, alt
        
    def get_limb_tangent_lla_brent(self, sat_x, sat_y, sat_z, los_x, los_y, los_z, date):
        """
        [最硬核的几何] 解算临边视线在 WGS84 椭球体上的真实切点经纬度与高度
        
        :param sat_x, y, z: 卫星在 ECEF 系下的坐标
        :param los_x, y, z: 相机视线(Line of Sight)在 ECEF 系下的方向单位矢量
        :return: (切点纬度, 切点经度, 切点WGS84绝对高度)
        """

        p_sat = Vector3D(float(sat_x), float(sat_y), float(sat_z))
        v_los_raw = Vector3D(float(los_x), float(los_y), float(los_z))
        v_los = v_los_raw.scalarMultiply(1.0 / v_los_raw.getNorm())
        
        d_guess = -p_sat.dotProduct(v_los)
        if d_guess <= 0:
            return np.nan, np.nan, np.nan

        # 1. 定义一个仅接收标量 d (行进距离)，返回绝对高度的目标函数
        def altitude_objective_func(d):
            # 将 numpy 的 float64 显式转为 Python 内置 float，防止 Java 接口报错
            p_test = p_sat.add(float(d), v_los)
            return self.earth.transform(p_test, self.ecef_frame, date).getAltitude()

        # 2. 召唤 Brent 方法！在猜测点的前后 50km 进行极速逼近
        # method='bounded' 就是带边界约束的优化，绝配这种问题
        res = minimize_scalar(
            altitude_objective_func, 
            bounds=(d_guess - 50000, d_guess + 50000), 
            method='bounded',
            options={'xatol': 1e-4}  # 设定收敛容差为 0.1 毫米
        )

        # 3. 提取极其变态精确的最优距离
        best_d_rigorous = res.x

        # 4. 算最终经纬度
        p_tangent = p_sat.add(float(best_d_rigorous), v_los)
        tangent_pt = self.earth.transform(p_tangent, self.ecef_frame, date)
        
        return math.degrees(tangent_pt.getLatitude()), math.degrees(tangent_pt.getLongitude()), tangent_pt.getAltitude()
    
    def is_in_eclipse(self, p_x, p_y, p_z, date):
        """
        判定空间给定点在指定时刻是否处于地影中 (考虑地球遮挡)
        
        :param p_x, p_y, p_z: 待测点的 ECEF 坐标
        :param date: AbsoluteDate 时间
        :return: bool (True 为在阴影中, False 为在日照中)
        """
        p_target = Vector3D(float(p_x), float(p_y), float(p_z))
        
        # 1. 获取太阳在 ECEF 系下的实时绝对坐标
        sun_pos_ecef = self.sun.getPVCoordinates(date, self.ecef_frame).getPosition()
        
        # 2. 构建一根从“目标点”连向“太阳”的数学直线 (Line 对象, 1e-10 是容差)
        line_of_sight = Line(p_target, sun_pos_ecef, 1e-10)
        
        # 3. 传入合法的 Line 对象，调用地球模型的严密相交算法
        # 返回的是离 p_target 最近的那个表面交点 (GeodeticPoint)
        intersection_gp = self.earth.getIntersectionPoint(
            line_of_sight, p_target, self.ecef_frame, date
        )
        
        # 连无限长的直线都没碰到地球，那绝对是毫无遮挡的日照区！
        if intersection_gp is None:
            return False
            
        # 4. 【排雷判定】必须确认这个交点是在“去往太阳的路上”，而不是在我们背后！
        # 把交点的经纬度转回 ECEF 的 3D 坐标
        inter_ecef = self.earth.transform(intersection_gp)
        
        # 算出向量：我们指向交点
        vec_to_inter = inter_ecef.subtract(p_target)
        # 算出向量：我们指向太阳
        vec_to_sun = sun_pos_ecef.subtract(p_target)
        
        # 如果点乘大于0，说明交点和太阳在同一侧（确实挡住了光线）
        is_same_direction = vec_to_inter.dotProduct(vec_to_sun) > 0
        
        return is_same_direction