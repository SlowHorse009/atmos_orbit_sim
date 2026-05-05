import math
import numpy as np
from scipy.optimize import root_scalar
from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore
from org.orekit.utils import Constants # type: ignore

class DynamicAttitudeController:
    """
    临边探测卫星动态姿态控制器
    
    架构特性：
    1. 动态主控轴滞回 (Hysteresis)：防止敏感度相近时的主控轴高频颤振，保护硬件寿命。
    2. O(1) 视野极值断言：在全域搜索前进行物理边界探测，避免盲目迭代导致的算力黑洞。
    3. 自适应热启动 (Warm-Start)：根据当前姿态自动收缩搜索圈层，提升常规推演性能。
    """

    def __init__(self, 
                 mode: str = 'DYNAMIC', 
                 target_alt_km: float = 400.0, 
                 locked_angle_deg: float = None, 
                 enable_noise: bool = False,
                 drift_rate_arcsec_s: float = 0.05, 
                 jitter_3sigma_arcsec: float = 1.5, 
                 orbital_period_sec: float = 5400.0):
        """
        初始化智能姿态控制器，注入任务目标与平台环境参数
        
        [控制模式与目标]
        :param mode: 工作模式 ['DYNAMIC', 'LOCKED']。
        :param target_alt_km: 期望探测的临边大气切点高度 (km)。
        :param locked_angle_deg: 期望硬锁死的【主控轴角度】(度)。仅 LOCKED 模式有效。
        
        [物理扰动平台参数]
        :param enable_noise: 是否在指令上叠加物理平台扰动 (默认 False)。
        :param drift_rate_arcsec_s: 低频热漂移率 (角秒/秒)。
        :param jitter_3sigma_arcsec: 高频微振动 3-sigma 阈值 (角秒)。
        :param orbital_period_sec: 标称轨道周期，用于热漂移正弦建模 (秒)。
        """
        self.mode = mode.upper()
        self.target_alt_m = (target_alt_km * 1000.0) if target_alt_km is not None else 400000.0
        self.locked_angle_deg = locked_angle_deg
        
        self.enable_noise = enable_noise
        self.drift_rate_deg = drift_rate_arcsec_s / 3600.0
        self.jitter_1sigma_deg = (jitter_3sigma_arcsec / 3.0) / 3600.0
        self.orbital_period_sec = orbital_period_sec

        if self.mode not in ['DYNAMIC', 'LOCKED']:
            raise ValueError(f"姿态控制器不支持的模式: {mode}")

        # [状态机与性能缓存]
        self._is_angle_locked = False
        if self.mode == 'LOCKED' and self.locked_angle_deg is not None:
            self._is_angle_locked = True
            
        self._dominant_axis = None  
        self._last_angle_guess = 0.0

    def _calc_ideal_body_attitude_rigorous(self, pos_ecef, vel_ecef, geodesy_engine, optics_sys, date, t_sec):
        """
        [单轴寻优求解器] 闭环求解平台理想姿态角
        
        :param pos_ecef, vel_ecef: ECEF 系绝对位置与速度
        :param geodesy_engine: 大地测量引擎 (WGS84)
        :param optics_sys: 光学载荷物理模型
        :param date: 当前绝对历元
        :param t_sec: 飞行相对时间，用于触发周期性主控轴重评估
        
        :return: (sat_roll_deg, sat_pitch_deg, sat_yaw_deg) 三轴姿态指令
        """
        x_dir, y_dir, z_dir = optics_sys._build_local_orbital_frame(pos_ecef, vel_ecef)
        earth_omega = Vector3D(0.0, 0.0, Constants.WGS84_EARTH_ANGULAR_VELOCITY)
        vel_absolute = vel_ecef.add(Vector3D.crossProduct(earth_omega, pos_ecef))

        def get_alt_at_attitude(test_roll_deg, test_pitch_deg):
            """内部闭包：测试特定姿态下的切点高度"""
            test_los_ecef = optics_sys._get_true_los_vector(
                x_dir, y_dir, z_dir, 
                sat_roll_rad=math.radians(test_roll_deg), 
                sat_pitch_rad=math.radians(test_pitch_deg), 
                sat_yaw_rad=0.0
            )
            los_physical = optics_sys.apply_velocity_aberration(test_los_ecef, vel_absolute)
            _, _, alt_actual, _ = geodesy_engine.get_limb_tangent_lla_brent(
                pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
                los_physical.getX(), los_physical.getY(), los_physical.getZ(), 
                date
            )
            return alt_actual

        # ==========================================
        # 主控轴滞回评估 (防颤振)
        # ==========================================
        # 首帧或每隔 60 秒做一次环境敏感度扫描
        if self._dominant_axis is None or t_sec % 60 == 0:
            delta = 0.01  
            # 中心对称差分计算雅可比敏感度
            alt_r_plus = get_alt_at_attitude(delta, 0.0)
            alt_r_minus = get_alt_at_attitude(-delta, 0.0)
            d_roll = abs((alt_r_plus - alt_r_minus) / 2.0)
            
            alt_p_plus = get_alt_at_attitude(0.0, delta)
            alt_p_minus = get_alt_at_attitude(0.0, -delta)
            d_pitch = abs((alt_p_plus - alt_p_minus) / 2.0)
            
            # 施加 Hysteresis (滞回) 阈值，保护控制器状态稳定性
            threshold = 1.2
            new_axis = self._dominant_axis
            if self._dominant_axis is None:
                new_axis = 'ROLL' if d_roll > d_pitch else 'PITCH'
            else:
                if d_roll > d_pitch * threshold:
                    new_axis = 'ROLL'
                elif d_pitch > d_roll * threshold:
                    new_axis = 'PITCH'
            
            if self._dominant_axis != new_axis:
                self._dominant_axis = new_axis
                print(f"[t={t_sec}s] 主控轴切换发生 | 滞回阈值验证通过 | 当前敏感轴: {self._dominant_axis}")

        # 封装寻优残差函数
        def altitude_residual(test_angle_deg):
            if self._dominant_axis == 'ROLL':
                return get_alt_at_attitude(test_angle_deg, 0.0) - self.target_alt_m
            else:
                return get_alt_at_attitude(0.0, test_angle_deg) - self.target_alt_m

        # ==========================================
        # 自适应区间 + O(1) 极值校验
        # ==========================================
        center = self._last_angle_guess
        # 物理感知：动态收缩热启动圈层
        span_tight = max(2.0, abs(center) * 0.15) 
        
        try:
            # 阶段 A：极速热启动 (99% 的帧会在这里 O(1) 收敛退出)
            res = root_scalar(
                altitude_residual, 
                bracket=[center - span_tight, center + span_tight], 
                method='brentq', 
                xtol=1e-4  
            )
            optimal_angle = res.root
            
        except ValueError:
            # 阶段 B：热启动失效。触发 O(1) 视野极限探测，避免陷入全域盲目搜索
            # 动态计算安全包线：平台极限机动角 + 硬件安装偏角 必须严格 < 89度
            base_mount_angle = math.degrees(abs(optics_sys.mount_roll if self._dominant_axis == 'ROLL' else optics_sys.mount_pitch))
            limit_angle = max(2.0, 89.0 - base_mount_angle)
            alt_min = altitude_residual(-limit_angle)
            alt_max = altitude_residual(limit_angle)
            
            # 如果极端两端的残差同号，说明整个物理空间内都不存在该高度的目标
            if alt_min * alt_max > 0:
                raise RuntimeError(
                    f"[视野丢失] 当前轨道高度与几何约束下，目标高程 {self.target_alt_m/1000}km 完全不可见！"
                )
            
            # 阶段 C：目标存在！且 [-89, 89] 天然成为绝对包围根的合法 bracket
            res = root_scalar(
                altitude_residual, 
                bracket=[-limit_angle, limit_angle], 
                method='brentq', 
                xtol=1e-4  
            )
            optimal_angle = res.root

        # 缓存状态并返回指令
        self._last_angle_guess = optimal_angle
        if self._dominant_axis == 'ROLL':
            return optimal_angle, 0.0, 0.0
        else:
            return 0.0, optimal_angle, 0.0

    def _generate_noise_model(self, t_sec, is_thrusting):
        """[内部私有方法] 生成高频抖动与低频热漂移噪声"""
        max_drift_amp = self.drift_rate_deg * (self.orbital_period_sec / 4.0) 
        thermal_drift = max_drift_amp * math.sin(2 * math.pi * t_sec / self.orbital_period_sec)
        high_freq_jitter = np.random.normal(0.0, self.jitter_1sigma_deg)
        thrust_offset = 0.005 if is_thrusting else 0.0
        return thermal_drift + (high_freq_jitter * (3.0 if is_thrusting else 1.0)) + thrust_offset

    def get_attitude_command(self, x, y, z, vx, vy, vz, geodesy_engine, optics_sys, date, t_sec=0.0, is_thrusting=False):
        """
        [对外统一核心接口] 智能获取平台三轴姿态控制指令
        
        :param x, y, z: ECEF 系绝对位置 (米)
        :param vx, vy, vz: ECEF 系绝对速度 (米/秒)
        :param geodesy_engine: WGS84 引擎实例
        :param optics_sys: 光学相机物理引擎实例
        :param date: 当前绝对历元
        :param t_sec: 已飞行秒数 (用于噪声注入与主控轴评估)
        :param is_thrusting: 当前是否推力机动
        """
        pos_ecef = Vector3D(float(x), float(y), float(z))
        vel_ecef = Vector3D(float(vx), float(vy), float(vz))
        
        # 1. 核心数学角解算
        if self.mode == 'DYNAMIC':
            ideal_roll, ideal_pitch, ideal_yaw = self._calc_ideal_body_attitude_rigorous(
                pos_ecef, vel_ecef, geodesy_engine, optics_sys, date, t_sec
            )
            
        elif self.mode == 'LOCKED':
            if not self._is_angle_locked:
                print(f"[快照锁死触发] 正在基于 t=0 空间几何测算...")
                ideal_roll, ideal_pitch, ideal_yaw = self._calc_ideal_body_attitude_rigorous(
                    pos_ecef, vel_ecef, geodesy_engine, optics_sys, date, t_sec
                )
                self.locked_angle_deg = ideal_roll if self._dominant_axis == 'ROLL' else ideal_pitch
                self._is_angle_locked = True
                print(f"[系统锁定] 平台主控轴 ({self._dominant_axis}) 已硬锁死于: {self.locked_angle_deg:.6f}°")
            else:
                ideal_roll = self.locked_angle_deg if self._dominant_axis == 'ROLL' else 0.0
                ideal_pitch = self.locked_angle_deg if self._dominant_axis == 'PITCH' else 0.0
                ideal_yaw = 0.0
        else:
            raise RuntimeError(f"姿控引擎异常：未知模式 '{self.mode}'！") 

        # 2. 噪声物理注入 (仅作用于激活的主控轴)
        noise_comp = self._generate_noise_model(t_sec, is_thrusting) if self.enable_noise else 0.0
        
        final_roll = ideal_roll + noise_comp if self._dominant_axis == 'ROLL' else ideal_roll
        final_pitch = ideal_pitch + noise_comp if self._dominant_axis == 'PITCH' else ideal_pitch
        final_yaw = ideal_yaw
        
        return final_roll, final_pitch, final_yaw, noise_comp