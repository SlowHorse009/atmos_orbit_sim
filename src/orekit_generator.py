import os
import pandas as pd
import numpy as np

# --- 基础核心包 ---
from org.orekit.orbits import KeplerianOrbit, PositionAngleType  # type: ignore
from org.orekit.frames import FramesFactory  # type: ignore
from org.orekit.time import TimeScalesFactory, AbsoluteDate  # type: ignore
from org.orekit.utils import Constants, IERSConventions  # type: ignore
from org.orekit.propagation import SpacecraftState  # type: ignore

# --- 1. 解析传播器 (Analytical) ---
from org.orekit.propagation.analytical import KeplerianPropagator, BrouwerLyddanePropagator  # type: ignore
from org.orekit.propagation.analytical.tle import TLE, TLEPropagator  # type: ignore

# --- 2. 数值传播器 (Numerical) ---
from org.orekit.propagation.numerical import NumericalPropagator  # type: ignore
from org.hipparchus.ode.nonstiff import DormandPrince853Integrator  # type: ignore
from org.orekit.forces.gravity import HolmesFeatherstoneAttractionModel  # type: ignore

# --- 3. 半解析传播器 (Semi-Analytical) ---
from org.orekit.propagation.semianalytical.dsst import DSSTPropagator  # type: ignore
from org.orekit.propagation.semianalytical.dsst.forces import DSSTZonal  # type: ignore

# --- 重力场提供者 ---
from org.orekit.forces.gravity.potential import GravityFieldFactory  # type: ignore

class OrekitOrbitGenerator:
    """
    全能型航天动力学星历生成器 (支持 Analytical, Numerical, Semi-Analytical, SGP4)
    """
    def __init__(self, prop_model='HPOP', 
                 a=None, e=None, i=None, raan=None, arg_pe=None, m0=None, 
                 start_year=2026, start_month=4, start_day=28, 
                 tle_line1=None, tle_line2=None,
                 gravity_degree=6, gravity_order=6, mass=1000.0):
        """
        :param prop_model: 选择传播器模型 
               ['KEPLERIAN', 'BL', 'SGP4', 'HPOP', 'DSST']
        :param a, e, i, raan, arg_pe, m0: 开普勒六根数 (SGP4 模式下可忽略)
        :param tle_line1, tle_line2: TLE 字符串 (仅 SGP4 模式需要)
        :param gravity_degree, gravity_order: 重力场阶数和次数
        :param mass: 卫星质量 (kg)
        """
        self.prop_model = prop_model.upper()
        self.mass = mass
        
        self.utc = TimeScalesFactory.getUTC()
        self.eci_frame = FramesFactory.getEME2000()
        self.ecef_frame = FramesFactory.getITRF(IERSConventions.IERS_2010, True)

        # ==========================================
        # 路由 1: SGP4 传播器 (基于 TLE)
        # ==========================================
        if self.prop_model == 'SGP4':
            if not tle_line1 or not tle_line2:
                raise ValueError("SGP4 模型必须传入 tle_line1 和 tle_line2 参数！")
            tle = TLE(tle_line1, tle_line2)
            self.propagator = TLEPropagator.selectExtrapolator(tle)
            # SGP4 的起始时间由 TLE 内部历元决定
            self.initial_date = tle.getDate()
            
        # ==========================================
        # 路由 2: 六根数驱动的传播器 (解析/数值/半解析)
        # ==========================================
        else:
            if a is None:
                raise ValueError(f"{self.prop_model} 模型必须传入开普勒六根数！")
                
            self.initial_date = AbsoluteDate(start_year, start_month, start_day, 12, 0, 0.0, self.utc)
            self.orbit = KeplerianOrbit(
                float(a), float(e), float(i), float(arg_pe), float(raan), float(m0),
                PositionAngleType.MEAN, self.eci_frame, self.initial_date, Constants.WGS84_EARTH_MU
            )

            # --- A. 解析模型 (Analytical) ---
            if self.prop_model == 'KEPLERIAN':
                self.propagator = KeplerianPropagator(self.orbit)
                
            elif self.prop_model == 'BL':
                # Brouwer-Lyddane (要求非归一化重力场，推荐 J2~J5)
                provider = GravityFieldFactory.getUnnormalizedProvider(min(gravity_degree, 5), 0)
                self.propagator = BrouwerLyddanePropagator(self.orbit, self.mass, provider)

            # --- B. 半解析模型 (Semi-Analytical) ---
            elif self.prop_model == 'DSST':
                # DSST 需要积分器来积分慢变量
                integrator = DormandPrince853Integrator(0.001, 1000.0, 1e-5, 1e-5)
                self.propagator = DSSTPropagator(integrator)
                self.propagator.setInitialState(SpacecraftState(self.orbit, self.mass), False) # 设为 Osculating 初始状态
                
                # DSST 使用专用的带谐项力模型 (Zonal)
                provider = GravityFieldFactory.getUnnormalizedProvider(gravity_degree, gravity_order)
                self.propagator.addForceModel(DSSTZonal(provider))

            # --- C. 数值模型 (Numerical) ---
            elif self.prop_model == 'HPOP':
                integrator = DormandPrince853Integrator(0.001, 1000.0, 1e-5, 1e-5)
                self.propagator = NumericalPropagator(integrator)
                self.propagator.setInitialState(SpacecraftState(self.orbit, self.mass))
                
                # HPOP 使用归一化重力场，极其精确
                provider = GravityFieldFactory.getNormalizedProvider(gravity_degree, gravity_order)
                gravity_model = HolmesFeatherstoneAttractionModel(self.ecef_frame, provider)
                self.propagator.addForceModel(gravity_model)
                
            else:
                raise ValueError(f"不支持的传播模型: {prop_model}")

    def generate_ephemeris_dataframe(self, duration_sec, step_sec):
        """通用轨道推演接口"""
        times_sec = np.arange(0, duration_sec + step_sec, step_sec)
        data = []

        print(f"🚀 [Orekit 全能引擎] 正在使用 {self.prop_model} 模型推演轨道...")
        
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