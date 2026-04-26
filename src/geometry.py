import numpy as np
import math

def calculate_tangent_point_ecef(pos_km, vel_km, alpha_deg, r_earth_km=6371.0):
    """
    已知卫星在地固系下的位置和速度，计算侧向观测切点的经纬高。
    
    参数:
    pos_km: [X, Y, Z] 卫星在地固系(ECEF)下的坐标 (km)
    vel_km: [Vx, Vy, Vz] 卫星在地固系下的速度向量 (km/s)
    alpha_deg: 相机视线的下俯角 (度)
    
    返回:
    dict: 包含经度、纬度、切点高度和直线探测距离
    """
    pos = np.array(pos_km)
    vel = np.array(vel_km)
    
    # 1. 建立局部轨道坐标系 (Local Orbital Frame)
    # 天底方向 (指向地心)
    u_nadir = -pos / np.linalg.norm(pos)
    
    # 严格的水平沿轨方向 (排除掉轨道偏心率导致的径向速度)
    v_horizontal = vel - np.dot(vel, u_nadir) * u_nadir
    u_along = v_horizontal / np.linalg.norm(v_horizontal)
    
    # 侧向 (Cross-track) = 沿轨 × 天底 (满足右手定则)
    u_cross = np.cross(u_along, u_nadir)
    
    # 2. 构造视线向量 (Line of Sight)
    # 满足"速度与观测垂直"的约束，视线在 u_cross 和 u_nadir 平面内
    alpha_rad = math.radians(alpha_deg)
    u_los = math.cos(alpha_rad) * u_cross + math.sin(alpha_rad) * u_nadir
    
    # 3. 计算切点 (射线上距离地心最近的点)
    # 投影距离 d = - (位置向量 · 视线向量)
    d_tangent = -np.dot(pos, u_los)
    
    # 切点三维坐标 (ECEF)
    tangent_pos = pos + d_tangent * u_los
    
    # 4. ECEF 坐标转经纬度 (使用球体近似)
    r_tangent = np.linalg.norm(tangent_pos)
    h_tg = r_tangent - r_earth_km
    
    lat_rad = math.asin(tangent_pos[2] / r_tangent)
    lon_rad = math.atan2(tangent_pos[1], tangent_pos[0])
    
    return {
        'lat': math.degrees(lat_rad),
        'lon': math.degrees(lon_rad),
        'h_tg': h_tg,
        'distance': d_tangent
    }

# --- 测试模块 (追加在 __main__ 中) ---
if __name__ == "__main__":
    # 我们用一个极简的赤道轨道来验证算法
    # 假设卫星在赤道上空 500km，经度 0度，正向东飞行
    test_pos = [6371.0 + 500.0, 0.0, 0.0]  # ECEF X轴上
    test_vel = [0.0, 7.5, 0.0]             # 沿 Y轴正向飞 (向东)
    
    # 测试下俯角 21.55 度
    test_alpha = 21.55 
    
    result = calculate_tangent_point_ecef(test_pos, test_vel, test_alpha)
    
    print(f"\n=== 三维侧向切点解算测试 ===")
    print(f"输入卫星坐标: {test_pos} km (赤道, 本初子午线)")
    print(f"输入飞行方向: 向东飞行")
    print(f"相机侧视下俯角: {test_alpha} 度")
    print("-" * 30)
    print(f"输出切点纬度: {result['lat']:.2f} 度 (正代表北半球，负代表南半球)")
    print(f"输出切点经度: {result['lon']:.2f} 度")
    print(f"输出切点高度: {result['h_tg']:.2f} km")
    print(f"直线探测距离: {result['distance']:.2f} km")