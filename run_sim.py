from src.simulation_engine import SimulationEngine

engine = SimulationEngine() # 自动搞定 JVM 和路径
file_path = engine.run_task("config_template.json") # 前端拿到跑完的 parquet 文件路径