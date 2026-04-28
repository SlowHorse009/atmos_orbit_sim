import math
import numpy as np

# 导入 Orekit 相关的几何与地球模型类
from org.orekit.models.earth import ReferenceEllipsoid # type: ignore
from org.orekit.frames import FramesFactory # type: ignore
from org.orekit.utils import IERSConventions # type: ignore
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore

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

    def get_limb_tangent_lla(self, sat_x, sat_y, sat_z, los_x, los_y, los_z, date):
        """
        [最硬核的几何] 解算临边视线在 WGS84 椭球体上的真实切点经纬度与高度
        
        :param sat_x, y, z: 卫星在 ECEF 系下的坐标
        :param los_x, y, z: 相机视线(Line of Sight)在 ECEF 系下的方向单位矢量
        :return: (切点纬度, 切点经度, 切点WGS84绝对高度)
        """
        p_sat = Vector3D(float(sat_x), float(sat_y), float(sat_z))
        v_los_raw = Vector3D(float(los_x), float(los_y), float(los_z))
        v_los = v_los_raw.scalarMultiply(1.0 / v_los_raw.getNorm())
        
        # 在严密的椭球几何中，切点(最低点)的特性是：
        # 该点的地心向径(Radius Vector) 与 视线矢量(LOS) 垂直。
        # 这里用向量投影的解析法，求出沿视线方向到达切点的距离 d
        # d = - (P_sat · V_los) 
        d_tangent = -p_sat.dotProduct(v_los)
        
        if d_tangent <= 0:
            # 说明看反了，看向了太空
            return np.nan, np.nan, np.nan
            
        # P_tangent = P_sat + d * V_los
        p_tangent = p_sat.add(d_tangent, v_los)
        
        # 将算出的三维切点坐标，再次扔进 WGS84 转换器求经纬度高程
        tangent_pt = self.earth.transform(p_tangent, self.ecef_frame, date)
        
        t_lat = math.degrees(tangent_pt.getLatitude())
        t_lon = math.degrees(tangent_pt.getLongitude())
        t_alt = tangent_pt.getAltitude()
        
        return t_lat, t_lon, t_alt