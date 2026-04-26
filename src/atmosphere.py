import math
from datetime import datetime
from nrlmsise00 import msise_model

# 玻尔兹曼常数 (J/K)
K_B = 1.380649e-23 

def get_atmospheric_params(dt_utc, alt_km, lat_deg, lon_deg, f107a=150, f107=150, ap=4):
    """
    调用 NRLMSISE-00 模型计算指定空间点的大气参数。
    
    参数:
    dt_utc: datetime 对象，UTC 时间
    alt_km: 海拔高度 (km)
    lat_deg: 纬度 (度)
    lon_deg: 经度 (度)
    f107a, f107, ap: 太阳辐射和地磁活动指数 (默认采用中等太阳活动水平)
    
    返回:
    dict: 包含温度、压强、总质量密度和原子氧密度的字典
    """
    # 调用核心模型
    # 返回值 ds 是各成分密度(cm^-3)列表，ts 是温度列表
    ds, ts = msise_model(dt_utc, alt_km, lat_deg, lon_deg, f107a, f107, ap)
    
    # 1. 温度 (K)
    local_temp_k = ts[1]  # ts[0] 是外逸层顶温度, ts[1] 是局部实际温度
    
    # 2. 计算总粒子数密度 (将各种气体分子/原子相加)
    # 索引对应: 0:He, 1:O, 2:N2, 3:O2, 4:Ar, 6:H, 7:N, 8:Anomalous_O
    number_densities_cm3 = [ds[0], ds[1], ds[2], ds[3], ds[4], ds[6], ds[7], ds[8]]
    total_n_cm3 = sum(number_densities_cm3)
    
    # 将体积单位转为立方米 (m^-3)
    total_n_m3 = total_n_cm3 * 1e6
    
    # 3. 根据理想气体状态方程计算压强 (Pa) -> P = n * K_B * T
    pressure_pa = total_n_m3 * K_B * local_temp_k
    
    # 4. 提取质量密度 (原始单位 g/cm^3 -> 转化为 kg/m^3)
    mass_density_kg_m3 = ds[5] * 1000.0
    
    return {
        'Temp_K': local_temp_k,
        'Pressure_Pa': pressure_pa,
        'Density_kg_m3': mass_density_kg_m3,
        'O_density_cm3': ds[1]  # 原子氧浓度 (对评估镜头腐蚀极具参考价值)
    }

# --- 测试模块 ---
if __name__ == "__main__":
    test_time = datetime(2026, 4, 26, 12, 0, 0)
    
    # 测试 1: 卫星本体环境 (约 500km)
    sat_env = get_atmospheric_params(test_time, alt_km=500.0, lat_deg=0.0, lon_deg=0.0)
    print("=== 卫星本体环境 (500 km) ===")
    print(f"温度: {sat_env['Temp_K']:.2f} K")
    print(f"压强: {sat_env['Pressure_Pa']:.2e} Pa (极高真空)")
    print(f"原子氧密度: {sat_env['O_density_cm3']:.2e} cm^-3")
    
    print("-" * 30)
    
    # 测试 2: 视线切点环境 (约 20km 平流层)
    target_env = get_atmospheric_params(test_time, alt_km=20.0, lat_deg=21.5, lon_deg=0.0)
    print("=== 观测切点环境 (20 km) ===")
    print(f"温度: {target_env['Temp_K']:.2f} K")
    print(f"压强: {target_env['Pressure_Pa']:.2e} Pa")