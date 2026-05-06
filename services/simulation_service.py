import uuid
import threading
import glob
import os
from core.simulation_engine import SimulationEngine
from utils_io.parquet_writer import save_parquet

# 配置：保留最近 N 个 parquet 文件
KEEP_LAST_N = 3
PARQUET_PATTERN = "output/*.parquet"


def _keep_last_n_parquet(pattern: str = PARQUET_PATTERN, n: int = KEEP_LAST_N):
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    deleted = []
    # 保留最新的 n 个，删除其余
    for f in files[n:]:
        try:
            os.remove(f)
            deleted.append(f)
        except Exception:
            # 忽略单个文件删除错误
            pass
    return deleted

# 现在的状态字典存的是详细数据
JOB_STATUS_STORE = {}

def _background_worker(job_id: str, config: dict):
    try:
        # 每次任务开始前清理旧的 parquet（保留最近 KEEP_LAST_N 个）并记录被删除的文件
        deleted_start = _keep_last_n_parquet()
        JOB_STATUS_STORE[job_id]["deleted_files_at_start"] = deleted_start

        # 1. 准备汇报工具（闭包函数）
        def update_progress(current, total):
            # 引擎一旦调用这个函数，就立刻更新黑板上的数字
            JOB_STATUS_STORE[job_id]["current"] = current
            JOB_STATUS_STORE[job_id]["total"] = total
            
        engine = SimulationEngine(config)
        # 2. 把汇报工具传给物理引擎
        df_results = engine.run_simulation(progress_callback=update_progress)

        # 确保输出目录存在
        os.makedirs("output", exist_ok=True)
        output_path = f"output/{job_id}.parquet"
        save_parquet(df_results, output_path)

        # 保存后再清理一次，确保目录中只保留最近 N 个文件；把删除清单写回状态
        deleted_after = _keep_last_n_parquet()
        JOB_STATUS_STORE[job_id]["deleted_files"] = deleted_after
        
        JOB_STATUS_STORE[job_id]["status"] = "SUCCESS"
        
    except Exception as e:
        JOB_STATUS_STORE[job_id] = {"status": "FAILED", "msg": str(e)}

def run_simulation_job(config: dict) -> str:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    # 初始化状态时，把进度也写进去
    JOB_STATUS_STORE[job_id] = {
        "status": "RUNNING", 
        "current": 0, 
        "total": 100 
    }
    
    worker_thread = threading.Thread(target=_background_worker, args=(job_id, config))
    worker_thread.daemon = True 
    worker_thread.start()

    return job_id

# 返回整个字典
def get_job_info(job_id: str) -> dict:
    return JOB_STATUS_STORE.get(job_id, {"status": "NOT_FOUND"})