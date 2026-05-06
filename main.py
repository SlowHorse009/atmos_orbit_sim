import time
import sys
from utils_io.config_loader import load_config
from services.simulation_service import run_simulation_job, get_job_info
from services.result_service import get_job_summary

def main():
    print("="*60)
    print("AtmosOrbitSim V4.0 (Desktop GUI Version)")
    print("="*60)
    
    config_path = "configs/config_tc01_dynamic_side.json" 
    
    try:
        config = load_config(config_path)
        job_id = run_simulation_job(config)
        
        print("\n正在进行轨道推演...\n")
        
        # 模拟桌面软件前端的 UI 渲染循环
        while True:
            # 前端每 0.1 秒来拿一次详细信息
            info = get_job_info(job_id)
            status = info.get("status")
            
            if status == "RUNNING":
                current = info.get("current", 0)
                total = info.get("total", 1) # 防除0
                pct = (current / total) * 100
                
                # 在终端画出物理进度条
                # '\r' 的作用是每次打印都回到行首覆盖，从而产生动画效果
                bar_length = 40
                filled_len = int(bar_length * current // total)
                bar = '█' * filled_len + '░' * (bar_length - filled_len)
                
                # 打印进度条
                sys.stdout.write(f'\r[前端 UI 渲染] 进度: |{bar}| {pct:.1f}% ({current}/{total} 帧)')
                sys.stdout.flush()
                
                time.sleep(0.1) # UI 刷新率：10 FPS
                
            elif status == "SUCCESS":
                sys.stdout.write(f'\r[前端 UI 渲染] 进度: |{"█"*40}| 100.0% 完美完成！\n')
                break
            elif status == "FAILED":
                print(f"\n计算崩溃！抛出弹窗: {info.get('msg')}")
                return
        
        summary = get_job_summary(job_id)
        print("\n数据提取成功！进入 3D 渲染界面...")
        print(f"靶心追踪平均高度: {summary['data']['tangent_alt_km']['mean']} km")
        print("="*60)
        
    except Exception as e:
        print(f"\n启动失败: {e}")

if __name__ == "__main__":
    main()