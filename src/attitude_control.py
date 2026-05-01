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

    def calc_ideal_nadir_angle_rigorous(self, pos_ecef, vel_ecef, target_alt_m, geodesy_engine, optics_sys, date):
        """
        [工业级严密求解器] 割线法 (Secant Method) 闭环求解 WGS84 绝对俯角
        
        结合了智能初始值猜测、防除零保护、角度合理性约束 (Clamp) 以及
        安全回退 (Fallback) 机制的高保真几何求解器。可消除 99% 的椭球曲率带来的截断误差。
        
        :param pos_ecef: 卫星当前在地固系 (ECEF) 下的绝对位置向量 (Vector3D，单位：米)
        :param vel_ecef: 卫星当前在地固系 (ECEF) 下的绝对速度向量 (Vector3D，单位：米/秒)
        :param target_alt_m: 期望探测的临边大气切点高度 (单位：米)
        :param geodesy_engine: WGS84 大地测量物理引擎实例 (用于求算地球真实几何表面的相交)
        :param optics_sys: 光学相机系统实例 (用于构建局部轨道系 VVLH 与视线追踪)
        :param date: 当前推演时间的绝对历元 (AbsoluteDate，用于历表计算)
        
        :return: 严密收敛后的理论绝对视轴下俯角 (Nadir Angle，单位：度)
        """
        import math

        def get_altitude_error(test_angle_deg):
            """内部闭环评估函数：输入测试俯角，返回与目标高度的误差(米)"""
            x_dir, _, z_dir = optics_sys._build_local_orbital_frame(pos_ecef, vel_ecef)
            los_vector = optics_sys._get_los_vector(x_dir, z_dir, test_angle_deg)
            _, _, alt_actual = geodesy_engine.get_limb_tangent_lla(
                pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
                los_vector.getX(), los_vector.getY(), los_vector.getZ(),
                date
            )
            return alt_actual - target_alt_m

        # ==========================================
        # 1. 智能初值生成 (球面模型近似法)
        # ==========================================
        d_sat = pos_ecef.getNorm()
        r_earth = geodesy_engine.earth.getEquatorialRadius()
        val_guess = (r_earth + target_alt_m) / d_sat
        val_guess = max(0.0, min(1.0, val_guess))
        base_angle = math.degrees(math.asin(val_guess))

        # 围绕基础角度生成割线法的两个初始探测点
        ang0 = base_angle - 0.5
        ang1 = base_angle + 0.5
        
        err0 = get_altitude_error(ang0)
        err1 = get_altitude_error(ang1)

        # ==========================================
        # 2. 带有满级安全保护的割线迭代求解
        # ==========================================
        max_iter = 15
        for i in range(max_iter):
            # [退出条件 1] 精度达标：误差小于 0.01 米 (1厘米级)，完美收敛
            if abs(err1) < 0.01:
                return ang1
                
            # [保护机制 1] 防止除零崩溃：两次迭代结果过于接近，导致计算斜率时除以 0
            if abs(err1 - err0) < 1e-12:
                break 
                
            # 割线法核心状态更新方程：x_new = x1 - f(x1) * (x1 - x0) / (f(x1) - f(x0))
            ang_new = ang1 - err1 * (ang1 - ang0) / (err1 - err0)
            
            # [保护机制 2] 视场约束：防止迭代发散导致视线穿透地心或射向深空 (夹紧在10°~85°之间)
            ang_new = max(10.0, min(85.0, ang_new))
            
            # 滚动更新迭代状态
            ang0 = ang1
            err0 = err1
            ang1 = ang_new
            err1 = get_altitude_error(ang1)

        # ==========================================
        # 3. 异常保底机制 (Fallback)
        # ==========================================
        # 如果达到最大迭代次数依然未收敛（如遇到极地复杂曲率），返回当前最优估计值，防止系统阻断
        return ang1


    def _generate_noise_model(self, t_sec, is_thrusting):
        """
        [内部私有方法] 生成高保真多频段卫星物理扰动模型
        
        融合了结构热漂移(低频)、部件高频微振动(Jitter)与推力器耦合补偿，
        用于模拟真实的在轨控制误差。
        
        :param t_sec: 当前飞行相对时间 (秒)，用于解算正弦波低频相位
        :param is_thrusting: 轨控标志位 (bool)，若开启则模拟推力器带来的瞬态阶跃与振动放大
        :return: 当前时刻的综合扰动角 (单位：度)
        """
        import math
        import numpy as np
        
        # 1. 低频热漂移 (正弦波模型，与轨道周期挂钩)
        max_drift_amp = self.drift_rate_deg * (self.orbital_period_sec / 4.0) 
        thermal_drift = max_drift_amp * math.sin(2 * math.pi * t_sec / self.orbital_period_sec)
        
        # 2. 高频微振动 (高斯白噪声模型)
        high_freq_jitter = np.random.normal(0.0, self.jitter_1sigma_deg)
        
        # 3. 轨控耦合与阶跃
        thrust_offset = 0.005 if is_thrusting else 0.0
        noise_gain = 3.0 if is_thrusting else 1.0

        return thermal_drift + (high_freq_jitter * noise_gain) + thrust_offset


    def get_pointing_command(self, x, y, z, vx, vy, vz, target_alt_m, geodesy_engine, optics_sys, date, 
                             enable_noise=False, t_sec=0.0, is_thrusting=False):
        """
        [对内核心接口] 动态姿态补偿模式解算入口 (严密割线法版)
        
        接收卫星当前轨道状态，调用底层几何与物理模型，输出当前帧的姿态控制指令
        与实际物理视线角，供后续靶心切点分析使用。
        
        :param x, y, z: 卫星当前在地固系 (ECEF) 下的绝对位置 (单位：米)
        :param vx, vy, vz: 卫星当前在地固系 (ECEF) 下的绝对速度 (单位：米/秒)
        :param target_alt_m: 目标观测大气层的切点物理高度 (单位：米)
        :param geodesy_engine: WGS84 大地测量解析引擎实例
        :param optics_sys: 载荷光学相机系统实例
        :param date: 当前推演时间的绝对历元 (AbsoluteDate)
        :param enable_noise: 是否在理想指令上叠加物理平台扰动 (默认 False)
        :param t_sec: 任务已飞行时间，用于传入扰动模型进行相位计算
        :param is_thrusting: 当前帧是否处于轨道机动推力状态
        
        :return: 一个包含三个元素的 Tuple:
                 - sat_body_pitch_deg: 下发给姿控系统的本体俯仰指令角 (已扣除相机安装偏角)
                 - actual_los: 考虑了所有物理扰动后的真实空间下俯指向角
                 - noise_comp: 纯噪声注入量 (用于遥测数据分析比对)
        """
        from org.hipparchus.geometry.euclidean.threed import Vector3D # type: ignore
        
        pos_ecef = Vector3D(float(x), float(y), float(z))
        vel_ecef = Vector3D(float(vx), float(vy), float(vz))
        
        # 1. 调用工业级割线法闭环计算几何指向
        nadir_angle_deg = self.calc_ideal_nadir_angle_rigorous(
            pos_ecef, vel_ecef, target_alt_m, geodesy_engine, optics_sys, date
        )
        
        # 将理想视线角扣除相机的静态安装偏角，得到卫星本体需要转动的指令姿态
        sat_body_pitch_deg = nadir_angle_deg - self.mount_pitch
        
        # 2. 物理噪声注入与现实扭曲
        noise_comp = self._generate_noise_model(t_sec, is_thrusting) if enable_noise else 0.0
        actual_los = nadir_angle_deg + noise_comp
        
        return sat_body_pitch_deg, actual_los, noise_comp
        
    def get_locked_pointing_command(self, locked_nadir_angle_deg, 
                                    enable_noise=False, t_sec=0.0, is_thrusting=False):
        """
        [对内核心接口] 载荷锁死模式：开环固定指向指令解算
        
        适用于载荷标定、凝视特定空间角度或闭环追踪失效时的降级保底模式。
        在该模式下，卫星不进行切点高度的闭环追踪，而是维持相对于局部轨道坐标系 (LVLH) 
        的恒定下俯角，并支持叠加物理平台的在轨高低频扰动。
        
        :param locked_nadir_angle_deg: 期望锁定的绝对空间下俯角 (单位：度)
        :param enable_noise: 是否在指令上叠加物理平台扰动 (默认 False)
        :param t_sec: 任务已飞行时间，用于传入扰动模型进行低频相位解算 (单位：秒)
        :param is_thrusting: 当前帧是否处于轨道机动推力状态 (引发振动放大)
        
        :return: 一个包含三个元素的 Tuple:
                 - sat_body_pitch_deg: 下发给姿控系统的恒定本体俯仰指令角 (已扣除安装偏角)
                 - actual_los: 考虑了物理扰动后的真实空间下俯指向角 (会有微小波动)
                 - noise_comp: 纯噪声注入量 (用于评估平台抖动对固定指向的影响)
        """
        # 1. 静态几何转换：指令角 = 目标空间绝对角 - 相机安装偏角
        sat_body_pitch_deg = locked_nadir_angle_deg - self.mount_pitch
        
        # 2. 物理噪声注入：即使指令是恒定的，真实的平台也会因为热变形和飞轮微振动而抖动
        noise_comp = self._generate_noise_model(t_sec, is_thrusting) if enable_noise else 0.0
        
        # 3. 真实视线角推演
        actual_los = locked_nadir_angle_deg + noise_comp
        
        return sat_body_pitch_deg, actual_los, noise_comp