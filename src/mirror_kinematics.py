import numpy as np
import math

class PayloadMirrorAssembly:
    """
    载荷内部补偿镜运动学黑盒接口
    用于隔离未知的机械安装细节，向上层提供纯粹的光轴视线(LOS)偏移向量
    """
    def __init__(self, mount_roll=0.0, mount_pitch=0.0, mount_yaw=0.0):
        """
        :param mount_roll, mount_pitch, mount_yaw: 镜子基座相对于卫星本体坐标系的安装误差/标定偏角 (度)
        """
        # 预留的安装矩阵 (目前全设为0，等机械组给数据再填)
        self.mount_matrix = self._euler_to_matrix(mount_roll, mount_pitch, mount_yaw)
        
        # 假设补偿镜在两个频段工作时的“等效视线偏移角”
        # 这里的数值是暂定的，你需要根据几何模块反算出来填进去
        self.mirror_states = {
            "LOW_BAND": 0.0,      # 盯 105km 时，假设镜子在零位 (基准态)
            "HIGH_BAND": -3.5     # 盯 400km 时，假设镜子需要向上(负俯仰)抬起约 3.5度
        }

    def _euler_to_matrix(self, roll, pitch, yaw):
        """ 欧拉角转旋转矩阵 (3-1-2 顺序为例) """
        r, p, y = math.radians(roll), math.radians(pitch), math.radians(yaw)
        Rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
        Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
        Rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
        return Rz @ Rx @ Ry

    def get_optical_axis_offset(self, band_mode):
        """
        根据当前工作频段，返回补偿镜制造的附加俯仰偏移角
        """
        if band_mode not in self.mirror_states:
            return 0.0 # 切换状态时盲区
        
        # 这里为了简化，假设镜子只改变俯仰角(Pitch)
        # 实际工程中如果镜子斜着装，可以在这里加入 Roll 和 Yaw 的耦合运算
        return self.mirror_states[band_mode]