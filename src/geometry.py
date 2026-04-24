import math

def calculate_depression_angle(h_sat_km, h_tg_km, r_earth_km=6371.0):
    """
    计算侧视观测时的相机下俯角及探测距离。
    
    参数:
    h_sat_km: 卫星轨道高度 (km)
    h_tg_km: 目标大气切点高度 (km)
    r_earth_km: 地球平均半径 (km)
    
    返回:
    alpha_deg: 下俯角 (度)
    distance_km: 卫星到大气的直线探测距离 (km)
    """
    if h_tg_km >= h_sat_km:
        raise ValueError("大气切点高度必须严格小于卫星轨道高度")
        
    # 余弦定理计算角度
    cos_alpha = (r_earth_km + h_tg_km) / (r_earth_km + h_sat_km)
    alpha_rad = math.acos(cos_alpha)
    alpha_deg = math.degrees(alpha_rad)
    
    # 勾股定理计算直线视线距离
    distance_km = math.sqrt((r_earth_km + h_sat_km)**2 - (r_earth_km + h_tg_km)**2)
    
    return alpha_deg, distance_km

# --- 测试模块 ---
if __name__ == "__main__":
    # 假设卫星在 500 km 高度，探测 20 km 的大气层
    angle, dist = calculate_depression_angle(500, 20)
    print(f"轨道高度 500 km, 观测 20 km 切点:")
    print(f"相机需向下偏转: {angle:.2f} 度")
    print(f"视线直线距离: {dist:.2f} km")