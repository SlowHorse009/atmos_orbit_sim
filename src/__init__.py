# src/__init__.py
import os
import orekit
from orekit.pyhelpers import setup_orekit_curdir

# 1. 单例模式启动 JVM (保证全局只启动一次)
try:
    vm = orekit.getVMEnv()
    if vm is None:
        raise ValueError("VM not initialized")
except Exception:
    print("[包初始化] 正在唤醒 JVM 引擎...")
    orekit.initVM()
    
    # ==========================================
    # 架构升级：锚点绑定到当前 src 包
    # ==========================================
    # __file__ 现在指向的是 src/__init__.py
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 往上一级推导，找到真正的项目根目录
    PROJECT_ROOT = os.path.dirname(SRC_DIR)
    
    # 锁定 data 文件夹的绝对路径
    data_file = os.path.join(PROJECT_ROOT, "data", "orekit-data.zip")
    
    # 严密校验
    if not os.path.exists(data_file):
        raise FileNotFoundError(
            f"\n\n[环境错误] 核心引擎缺失物理基准数据！\n"
            f"引擎模块路径: {SRC_DIR}\n"
            f"期望数据路径: {data_file}\n"
            f"请确保已将 orekit-data.zip 放置在与 src 平级的 data 文件夹中！\n"
        )
        
    setup_orekit_curdir(data_file)
    print(f"[包初始化] Orekit 物理星历数据 (离线版) 挂载完毕！")

# 暴露核心类供外部调用
from .simulation_engine import SimulationEngine
__all__ = ["SimulationEngine"]