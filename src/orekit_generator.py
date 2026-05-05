import os
import pandas as pd
import numpy as np

# --- 基础核心包 ---
from org.orekit.orbits import KeplerianOrbit, PositionAngleType  # type: ignore
from org.orekit.frames import FramesFactory  # type: ignore
from org.orekit.time import TimeScalesFactory, AbsoluteDate  # type: ignore
from org.orekit.utils import Constants, IERSConventions  # type: ignore
from org.orekit.propagation import SpacecraftState  # type: ignore
from org.orekit.models.earth import ReferenceEllipsoid # type: ignore
from org.orekit.bodies import CelestialBodyFactory # type: ignore

# --- 1. 解析传播器 (Analytical) ---
from org.orekit.propagation.analytical import KeplerianPropagator, BrouwerLyddanePropagator  # type: ignore
from org.orekit.propagation.analytical.tle import TLE, TLEPropagator  # type: ignore

# --- 2. 数值传播器 (Numerical) 与 力模型 ---
from org.orekit.propagation.numerical import NumericalPropagator  # type: ignore
from org.hipparchus.ode.nonstiff import DormandPrince853Integrator  # type: ignore
from org.orekit.forces.gravity import HolmesFeatherstoneAttractionModel, ThirdBodyAttraction  # type: ignore
from org.orekit.forces.gravity.potential import GravityFieldFactory  # type: ignore
from org.orekit.forces.drag import DragForce # type: ignore
from org.orekit.models.earth.atmosphere import NRLMSISE00 # type: ignore
from org.orekit.models.earth.atmosphere.data import MarshallSolarActivityFutureEstimation # type: ignore
from org.orekit.forces.radiation import SolarRadiationPressure # type: ignore
from org.orekit.forces.drag import IsotropicDrag # type: ignore
from org.orekit.forces.radiation import IsotropicRadiationSingleCoefficient # type: ignore

class OrekitOrbitGenerator:
    """
    航天动力学星历生成器 (支持前端 JSON 动态路由分发)
    """
    def __init__(self, 
                 prop_model: str = 'TWOBODY', 
                 epoch_iso: str = "2026-04-28T12:00:00.000",
                 a: float = None, e: float = None, i: float = None, 
                 raan: float = None, arg_pe: float = None, m0: float = None, 
                 tle_line1: str = None, tle_line2: str = None,
                 mass_kg: float = 1000.0, cross_section_m2: float = 5.0, 
                 cd: float = 2.2, cr: float = 1.2,
                 gravity_degree: int = 6, gravity_order: int = 6, 
                 enable_thirdbody: bool = False, enable_drag: bool = False, enable_srp: bool = False):
        """
        [接口参数字典] 
        :param prop_model: 选择传播器模型 ['TWOBODY', 'ANALYTICAL', 'HPOP', 'SGP4']
        :param epoch_iso: 初始历元时间 (ISO8601 格式，如 "2026-04-28T12:00:00.000")
        
        [轨道状态参数]
        :param a, e, i, raan, arg_pe, m0: 开普勒六根数 (SGP4 模式下可忽略。长度单位: 米, 角度单位: 弧度)
        :param tle_line1, tle_line2: TLE 双行根数格式字符串 (仅 SGP4 模式必须)
        
        [航天器物理属性]
        :param mass_kg: 卫星本体质量 (kg)
        :param cross_section_m2: 卫星迎风/受光有效截面积 (平方米，用于阻力和光压)
        :param cd: 大气阻力系数 (通常在 2.0 ~ 2.2)
        :param cr: 太阳辐射压反射系数 (通常在 1.0 ~ 1.5)
        
        [高保真环境摄动开关 (仅 HPOP 模式有效)]
        :param gravity_degree, gravity_order: 地球非球形重力场阶数和次数 (ANALYTICAL 模式也共用此参数设置 J2-J5)
        :param enable_thirdbody: 是否开启日、月三体引力摄动 (计算极快，建议开启)
        :param enable_drag: 是否开启 NRLMSISE00 高精度大气阻力模型 (LEO 低轨必须开启)
        :param enable_srp: 是否开启太阳辐射压 (MEO/GEO 中高轨建议开启)
        """
        
        self.prop_model = prop_model.upper()
        # 卫星的宏观物理属性
        self.mass_kg = mass_kg
        self.cross_section_m2 = cross_section_m2
        self.cd = cd
        self.cr = cr
        
        # 1. 基础时空参考系搭建
        self.utc = TimeScalesFactory.getUTC()
        self.eci_frame = FramesFactory.getEME2000()
        self.ecef_frame = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
        self.earth_shape = ReferenceEllipsoid.getWgs84(self.ecef_frame)
        self.sun = CelestialBodyFactory.getSun()

        # ==========================================
        # 路由 1: SGP4 传播器 (基于 TLE)
        # ==========================================
        if self.prop_model == 'SGP4':
            if not tle_line1 or not tle_line2:
                raise ValueError("SGP4 模式必须传入 tle_line1 和 tle_line2 参数！")
            tle = TLE(tle_line1, tle_line2)
            self.propagator = TLEPropagator.selectExtrapolator(tle)
            self.initial_date = tle.getDate()
            
        # ==========================================
        # 路由 2: 六根数驱动的传播器 (解析 / 数值)
        # ==========================================
        else:
            if a is None:
                raise ValueError(f"{self.prop_model} 模式必须传入完整的开普勒六根数！")
                
            # 优雅地解析前端传来的 ISO 时间字符串 (去掉可能带有的 Z 时区标识)
            clean_epoch = epoch_iso.replace("Z", "")
            self.initial_date = AbsoluteDate(clean_epoch, self.utc)
            
            self.orbit = KeplerianOrbit(
                float(a), float(e), float(i), float(arg_pe), float(raan), float(m0),
                PositionAngleType.MEAN, self.eci_frame, self.initial_date, Constants.WGS84_EARTH_MU
            )

            # --- A. 理想双体模型 (Two-Body) ---
            if self.prop_model == 'TWOBODY':
                self.propagator = KeplerianPropagator(self.orbit)
                
            # --- B. 快速解析模型 (Analytical J2~J5) ---
            elif self.prop_model == 'ANALYTICAL':
                provider = GravityFieldFactory.getUnnormalizedProvider(min(gravity_degree, 5), 0)
                self.propagator = BrouwerLyddanePropagator(self.orbit, self.mass_kg, provider, 0.0)

            # --- C. 高保真数值模型 (HPOP) ---
            elif self.prop_model == 'HPOP':
                integrator = DormandPrince853Integrator(0.001, 1000.0, 1e-5, 1e-5)
                self.propagator = NumericalPropagator(integrator)
                self.propagator.setInitialState(SpacecraftState(self.orbit, self.mass_kg))
                
                # 1) 地球非球形重力场 (必选)
                provider = GravityFieldFactory.getNormalizedProvider(gravity_degree, gravity_order)
                gravity_model = HolmesFeatherstoneAttractionModel(self.ecef_frame, provider)
                self.propagator.addForceModel(gravity_model)
                
                # 2) 日月三体引力 (可选)
                if enable_thirdbody:
                    self.propagator.addForceModel(ThirdBodyAttraction(self.sun))
                    self.propagator.addForceModel(ThirdBodyAttraction(CelestialBodyFactory.getMoon()))
                
                # 3) 高精度大气阻力 (可选)
                if enable_drag:
                    csm = MarshallSolarActivityFutureEstimation(
                        MarshallSolarActivityFutureEstimation.DEFAULT_SUPPORTED_NAMES,
                        MarshallSolarActivityFutureEstimation.StrengthLevel.AVERAGE
                    )
                    atmosphere = NRLMSISE00(csm, self.sun, self.earth_shape)
                    isotropic_drag = IsotropicDrag(float(cross_section_m2), float(cd))
                    self.propagator.addForceModel(DragForce(atmosphere, isotropic_drag))
                    
                # 4) 太阳辐射压 (可选)
                if enable_srp:
                    sun = CelestialBodyFactory.getSun()
                    isotropic_radiation = IsotropicRadiationSingleCoefficient(float(self.cross_section_m2), float(self.cr))
                    
                    try:
                        # 尝试 Orekit 12+ 新架构：(太阳, 地球3D模型, 航天器)
                        srp = SolarRadiationPressure(sun, self.earth_shape, isotropic_radiation)
                    except Exception:
                        # 降级到 Orekit 11 老架构：(太阳, 地球赤道半径, 航天器)
                        srp = SolarRadiationPressure(sun, Constants.WGS84_EARTH_EQUATORIAL_RADIUS, isotropic_radiation)

                    self.propagator.addForceModel(srp)
            else:
                raise ValueError(f"不支持的传播模型: {prop_model}")

    def generate_ephemeris_dataframe(self, duration_sec, step_sec):
        """通用轨道推演接口"""
        times_sec = np.arange(0, duration_sec + step_sec, step_sec)
        data = []

        print(f"[Orekit 全能引擎] 正在使用 {self.prop_model} 模型推演轨道...")
        
        for t in times_sec:
            target_date = self.initial_date.shiftedBy(float(t))
            state = self.propagator.propagate(target_date)
            
            pv_ecef = state.getPVCoordinates(self.ecef_frame)
            pos = pv_ecef.getPosition()
            vel = pv_ecef.getVelocity()
            
            data.append([
                t, 
                pos.getX(), pos.getY(), pos.getZ(),
                vel.getX(), vel.getY(), vel.getZ()
            ])

        df = pd.DataFrame(data, columns=['time_sec', 'x', 'y', 'z', 'vx', 'vy', 'vz'])
        return df