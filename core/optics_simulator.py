import math
import numpy as np

# 引入 Java 底层 3D 向量库与严密旋转矩阵库
from org.hipparchus.geometry.euclidean.threed import Vector3D, Rotation, RotationConvention, RotationOrder # type: ignore
from org.orekit.utils import Constants # type: ignore

class LimbOpticsSimulator:
    """
    高保真临边观测光学映射解析器 
    """
    def __init__(self, fov_deg=None, focal_length_mm=None, sensor_size_mm=None,
                 mount_roll_deg=68.0, mount_pitch_deg=0.0, mount_yaw_deg=0.0):
        """
        初始化光学系统，绑定静态硬件属性
        
        :param fov_deg, focal_length_mm, sensor_size_mm: 光学视场参数
        :param mount_roll_deg: 相机侧滚安装角 (度)，决定前视还是侧视
        :param mount_pitch_deg: 相机俯仰安装角 (度)，决定前瞻角度
        :param mount_yaw_deg: 相机偏航安装角 (度)
        """
        # ==========================================
        # 1. 视场解析逻辑
        # ==========================================
        has_fov = fov_deg is not None
        has_lens = focal_length_mm is not None and sensor_size_mm is not None

        # 冲突检测
        if has_fov and has_lens:
            raise ValueError(
                "光学参数冲突：fov_deg 与 (focal_length_mm, sensor_size_mm) 不能同时提供"
            )

        # 模式 A：直接 FOV
        if has_fov:
            self.fov_deg = float(fov_deg)
            self.fov_rad = math.radians(self.fov_deg)

        # 模式 B：镜头推导
        elif has_lens:
            self.f_mm = float(focal_length_mm)
            self.sensor_size_mm = float(sensor_size_mm)

            self.fov_rad = 2.0 * math.atan(self.sensor_size_mm / (2.0 * self.f_mm))
            self.fov_deg = math.degrees(self.fov_rad)

        # 错误抛出
        else:
            raise ValueError(
                "缺少视场参数：必须提供 fov_deg 或 (focal_length_mm + sensor_size_mm)"
            )

        # ==========================================
        # 2. 硬件静态安装角入表
        # ==========================================
        self.mount_roll = math.radians(mount_roll_deg)
        self.mount_pitch = math.radians(mount_pitch_deg)
        self.mount_yaw = math.radians(mount_yaw_deg)

    def _build_local_orbital_frame(self, pos_ecef, vel_ecef):
        """
        构建局部轨道坐标系 (LVLH) - 引入 Reviewer 的强正交化规范
        """
        # Z轴 (天底方向)：指向地心
        z_vec = pos_ecef.scalarMultiply(-1.0)
        z_dir = z_vec.scalarMultiply(1.0 / z_vec.getNorm())
        
        # Y轴 (轨道法向)：位置与速度的叉乘
        y_vec = pos_ecef.crossProduct(vel_ecef)
        y_dir = y_vec.scalarMultiply(1.0 / y_vec.getNorm())
        
        # X轴 (飞行方向)：完成右手系
        x_vec = y_dir.crossProduct(z_dir)
        x_dir = x_vec.scalarMultiply(1.0 / x_vec.getNorm())
        
        return x_dir, y_dir, z_dir

    def _get_true_los_vector(self, x_dir, y_dir, z_dir, sat_roll_rad, sat_pitch_rad, sat_yaw_rad, fov_offset_rad=0.0):
        """
        [6-DOF 视线解算器] 将相机的静态安装与卫星的动态姿态严密叠加
        
        :param x_dir, y_dir, z_dir: LVLH 基向量
        :param sat_roll_rad, sat_pitch_rad, sat_yaw_rad: 卫星平台当前的动态指令姿态 (弧度)
        :param fov_offset_rad: 视场偏移角 (弧度)，用于在焦平面上扫掠上下边缘
        :return: 严密映射到 ECEF 3D 绝对空间中的 LOS 视线矢量
        """
        # 默认光轴指向天底 (+Z轴)
        camera_boresight = Vector3D.PLUS_K 
        
        # 1. 组装安装矩阵与姿态矩阵
        mount_rot = Rotation(
            RotationOrder.ZYX, RotationConvention.VECTOR_OPERATOR,
            self.mount_yaw, self.mount_pitch, self.mount_roll
        )
        
        body_rot = Rotation(
            RotationOrder.ZYX, RotationConvention.VECTOR_OPERATOR,
            sat_yaw_rad, sat_pitch_rad, sat_roll_rad
        )
        
        # 2. 算出没有任何偏移的靶心光线”(在 LVLH 坐标系下)
        total_rot = body_rot.applyTo(mount_rot)
        los_center_lvlh = total_rot.applyTo(camera_boresight)
        
        # 3.在 LVLH 空间中，围绕“地球真水平轴”上下扫掠
        if fov_offset_rad != 0.0:
            # 天底向量 (+Z轴) 叉乘中心视线
            # 得到的一定是一根完美平行于地球海平面、且垂直于视线的“真水平轴”
            earth_horizontal_axis = Vector3D.crossProduct(Vector3D.PLUS_K, los_center_lvlh)
            
            # 除非相机笔直看着地心(长度为0)，否则执行上下扫掠
            if earth_horizontal_axis.getNorm() > 1e-8:
                earth_horizontal_axis = earth_horizontal_axis.scalarMultiply(1.0 / earth_horizontal_axis.getNorm())
                
                # 绕着地球真水平轴旋转，保证视线绝对是“纯垂直海拔”扫掠
                fov_rot = Rotation(
                    earth_horizontal_axis, 
                    fov_offset_rad, 
                    RotationConvention.VECTOR_OPERATOR
                )
                los_final_lvlh = fov_rot.applyTo(los_center_lvlh)
            else:
                los_final_lvlh = los_center_lvlh
        else:
            los_final_lvlh = los_center_lvlh
            
        # 4. 将最终光线映射回 ECEF 绝对空间
        term_x = x_dir.scalarMultiply(los_final_lvlh.getX())
        term_y = y_dir.scalarMultiply(los_final_lvlh.getY())
        term_z = z_dir.scalarMultiply(los_final_lvlh.getZ())
        
        los_unnorm = term_x.add(term_y).add(term_z)
        return los_unnorm.scalarMultiply(1.0 / los_unnorm.getNorm())

    def calculate_altitude_range(self, x, y, z, vx, vy, vz, sat_roll_deg, sat_pitch_deg, sat_yaw_deg, geodesy_engine, date):
        """
        接收本体姿态，测算 FOV 包络内的最大最小切点高度
        """
        pos_ecef = Vector3D(float(x), float(y), float(z))
        vel_ecef = Vector3D(float(vx), float(vy), float(vz))
        
        # 1. 建立正交空间基底
        x_dir, y_dir, z_dir = self._build_local_orbital_frame(pos_ecef, vel_ecef)
        
        # 转弧度
        s_roll = math.radians(sat_roll_deg)
        s_pitch = math.radians(sat_pitch_deg)
        s_yaw = math.radians(sat_yaw_deg)
        
        # 半视场角
        fov_half = self.fov_rad / 2.0
        
        # 2. 调用 6-DOF 解算器获取绝对包络光线
        # 注意：视野的 bottom (低切点) 意味着视线需要更往下压，相当于 pitch 角度正向增加
        los_bottom_ecef = self._get_true_los_vector(x_dir, y_dir, z_dir, s_roll, s_pitch, s_yaw, fov_offset_rad=fov_half)
        los_top_ecef = self._get_true_los_vector(x_dir, y_dir, z_dir, s_roll, s_pitch, s_yaw, fov_offset_rad=-fov_half)
        
        # 3. 光行差相对论补偿 (公用绝对速度)
        earth_omega = Vector3D(0.0, 0.0, Constants.WGS84_EARTH_ANGULAR_VELOCITY)
        vel_absolute = vel_ecef.add(Vector3D.crossProduct(earth_omega, pos_ecef))
        
        los_bot_phys = self.apply_velocity_aberration(los_bottom_ecef, vel_absolute)
        los_top_phys = self.apply_velocity_aberration(los_top_ecef, vel_absolute)
        
        # 4. 使用 WGS84 引擎求交
        _, _, alt_min, _ = geodesy_engine.get_limb_tangent_lla_brent(
            pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
            los_bot_phys.getX(), los_bot_phys.getY(), los_bot_phys.getZ(),
            date
        )
        
        _, _, alt_max, _ = geodesy_engine.get_limb_tangent_lla_brent(
            pos_ecef.getX(), pos_ecef.getY(), pos_ecef.getZ(),
            los_top_phys.getX(), los_top_phys.getY(), los_top_phys.getZ(),
            date
        )
        
        return alt_min, alt_max
    
    def apply_velocity_aberration(self, los_cmd_ecef, vel_absolute):
        """
        [相对论补偿]
        """
        c = Constants.SPEED_OF_LIGHT
        v_over_c = Vector3D(1.0 / c, vel_absolute)
        
        los_physical_unnorm = los_cmd_ecef.subtract(v_over_c)
        return los_physical_unnorm.scalarMultiply(1.0 / los_physical_unnorm.getNorm())