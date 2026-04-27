import numpy as np
import math

def calculate_tangent_point_ecef(pos_km, vel_km, alpha_deg, r_earth_km=6371.0):
    """
    高精度侧向观测切点解算 (符合客户要求的非地表切点逻辑)。
    
    参数:
    pos_km: [X, Y, Z] 卫星在地固系(ECEF)下的坐标 (km)
    vel_km: [Vx, Vy, Vz] 卫星在地固系下的速度向量 (km/s)
    alpha_deg: 相机中心光轴的下俯角 (度)
    
    返回:
    dict: 包含经度、纬度、切点高度、探测距离及高精度光程参考
    """
    pos = np.array(pos_km)
    vel = np.array(vel_km)
    
    # 1. 建立局部轨道坐标系 (Local Orbital Frame)
    u_nadir = -pos / np.linalg.norm(pos)
    
    # 提取水平速度分量，构造沿轨向量
    v_horizontal = vel - np.dot(vel, u_nadir) * u_nadir
    u_along = v_horizontal / np.linalg.norm(v_horizontal)
    
    # 构造侧向向量 (Cross-track)
    u_cross = np.cross(u_along, u_nadir)
    
    # 2. 构造视线向量 (Line of Sight, LOS)
    alpha_rad = math.radians(alpha_deg)
    # 视线由侧向向量向下俯冲 alpha 角度
    u_los = math.cos(alpha_rad) * u_cross + math.sin(alpha_rad) * u_nadir
    
    # 3. 计算切点 (Tangent Point)
    # 这里的几何逻辑：在 3D 空间中寻找射线上距离地心最近的点
    # 该点与地心的连线必然垂直于视线向量 u_los
    d_tangent = -np.dot(pos, u_los)
    tangent_pos = pos + d_tangent * u_los
    
    # 4. 计算切点物理参数
    r_tangent = np.linalg.norm(tangent_pos)
    h_tg = r_tangent - r_earth_km  # 这就是公式中的 H_t
    
    # 5. 坐标转换 (ECEF -> LLA)
    # 纬度计算
    lat_rad = math.asin(tangent_pos[2] / r_tangent)
    # 经度计算
    lon_rad = math.atan2(tangent_pos[1], tangent_pos[0])
    
    return {
        'lat': math.degrees(lat_rad),
        'lon': math.degrees(lon_rad),
        'h_tg': h_tg,          # 探测点高度 (km)
        'distance': d_tangent, # 卫星到切点的直线距离 (km)
        'r_tg_vec': tangent_pos # 返回切点矢量用于后续更复杂的积分
    }

def calculate_path_length_high_precision(h_tg, delta_h, r_earth_km=6371.0):
    """
    回应客户要求的高精度光程计算公式：
    (R_e + H_t)^2 + (L/2)^2 = (R_e + H_t + delta_h)^2
    """
    r_base = r_earth_km + h_tg
    r_outer = r_base + delta_h
    
    half_l_sq = r_outer**2 - r_base**2
    if half_l_sq < 0: return 0.0
    
    return 2.0 * math.sqrt(half_l_sq)

# --- 验证模块 ---
if __name__ == "__main__":
    # 模拟卫星：500km高度，赤道上空
    test_pos = [6871.0, 0.0, 0.0]
    test_vel = [0.0, 7.5, 0.0]
    test_alpha = 10.98  # 使用之前的安全下俯角
    
    res = calculate_tangent_point_ecef(test_pos, test_vel, test_alpha)
    
    print(f"=== 客户级精度切点解算结果 ===")
    print(f"切点经纬度: {res['lon']:.2f}°, {res['lat']:.2f}°")
    print(f"切点高度 (H_t): {res['h_tg']:.2f} km")
    print(f"直线探测距离: {res['distance']:.2f} km")
    
    # 验证客户提到的光程逻辑
    L = calculate_path_length_high_precision(res['h_tg'], delta_h=300.0)
    print(f"在切点高度基础上，穿过300km厚度大气的路径长度: {L:.2f} km")