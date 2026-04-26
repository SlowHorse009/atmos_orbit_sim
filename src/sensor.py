import math

class GSENSE4040:
    PIXEL_SIZE_UM = 9.0        
    ARRAY_SIZE = 4096          
    SENSOR_SIZE_MM = 36.8      
    
    def __init__(self, focal_length_mm):
        self.focal_length_mm = focal_length_mm
        
    def get_ifov(self):
        pixel_size_mm = self.PIXEL_SIZE_UM / 1000.0
        return pixel_size_mm / self.focal_length_mm

    # --- 新增的反推函数 ---
    def calc_center_angle_from_bottom_height(self, h_sat_km, bottom_h_tg_km, r_earth_km=6371.0):
        """
        根据要求的最低观测高度，反推卫星中心光轴的安装/控制下俯角。
        """
        # 1. 计算看最低高度(比如 20km) 需要的绝对下俯角
        cos_alpha_bottom = (r_earth_km + bottom_h_tg_km) / (r_earth_km + h_sat_km)
        alpha_bottom_rad = math.acos(cos_alpha_bottom)
        
        # 2. 计算中心光轴与底部边缘的角度差
        ifov_rad = self.get_ifov()
        center_pixel = self.ARRAY_SIZE / 2.0
        angle_offset_rad = center_pixel * ifov_rad  # 半个靶面的视场角
        
        # 3. 中心光轴应该比底部边缘抬高一点 (即下俯角变小)
        alpha_center_rad = alpha_bottom_rad - angle_offset_rad
        
        return math.degrees(alpha_center_rad)
        
    def map_pixels_to_heights(self, h_sat_km, alpha_center_deg, r_earth_km=6371.0):
        # ... (保持原代码不变) ...
        ifov_rad = self.get_ifov()
        alpha_center_rad = math.radians(alpha_center_deg)
        center_pixel = self.ARRAY_SIZE / 2.0
        
        heights = []
        for i in range(self.ARRAY_SIZE):
            angle_offset_rad = (center_pixel - i) * ifov_rad
            alpha_i_rad = alpha_center_rad + angle_offset_rad
            h_tg_i = (r_earth_km + h_sat_km) * math.cos(alpha_i_rad) - r_earth_km
            heights.append(h_tg_i)
            
        return heights

# --- 更新后的测试模块 ---
if __name__ == "__main__":
    sensor = GSENSE4040(focal_length_mm=100.0)
    H_SAT = 500.0
    MIN_TARGET_H = 20.0
    
    # 1. 动态计算安全的中心下俯角
    safe_center_angle = sensor.calc_center_angle_from_bottom_height(H_SAT, MIN_TARGET_H)
    print(f"为了让最底边缘刚好贴住 {MIN_TARGET_H} km，中心光轴下俯角需设为: {safe_center_angle:.2f} 度")
    
    # 2. 用算出来的安全角度，重新映射所有像素的高度
    pixel_heights = sensor.map_pixels_to_heights(h_sat_km=H_SAT, alpha_center_deg=safe_center_angle)
    
    print("\n=== 修正后的像素高度映射 ===")
    print(f"第 0 行 (最底部视场) 观测高度: {pixel_heights[0]:.2f} km")
    print(f"第 2048 行 (中心光轴) 观测高度: {pixel_heights[2048]:.2f} km")
    print(f"第 4095 行 (最顶部视场) 观测高度: {pixel_heights[-1]:.2f} km")