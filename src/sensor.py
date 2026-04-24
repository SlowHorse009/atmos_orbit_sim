class GSENSE4040:
    PIXEL_SIZE_UM = 9.0        # 像元尺寸 9 μm
    ARRAY_SIZE = 4096          # 4096 x 4096 阵列
    SENSOR_SIZE_MM = 36.8      # 靶面尺寸 36.8 mm (大概值，可根据规格书修正)
    
    def __init__(self, focal_length_mm):
        self.focal_length_mm = focal_length_mm
        
    def get_ifov(self):
        """计算瞬时视场角 (Instantaneous Field of View) - 弧度"""
        # IFOV ≈ 像元尺寸 / 焦距
        pixel_size_mm = self.PIXEL_SIZE_UM / 1000.0
        return pixel_size_mm / self.focal_length_mm