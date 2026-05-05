# run_sim.py
from src.simulation_engine import SimulationEngine

if __name__ == "__main__":
    engine = SimulationEngine("configs/config_tc02_locked_forward.json")
    engine.run_simulation()
    # engine.export_analysis_report("tc02_results.csv")