import sys
import os
import matplotlib.pyplot as plt

# 把项目根目录加进系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.result_service import get_series_data

def plot_dashboard_mockup(job_id: str):
    """
    生成给前端做参考的四大面板图
    """
    print(f"正在提取任务 {job_id} 的数据进行本地绘图打样...")

    # ==========================================
    # 1. 模拟前端调用接口，获取四个图表所需的所有字段
    # ==========================================
    fields_needed = [
        "sat_lon", "sat_lat", "in_eclipse", 
        "tangent_alt_km", "fov_alt_min_km", "fov_alt_max_km",
        "sat_roll_deg", "sat_pitch_deg", "sat_yaw_deg", "attitude_noise_deg",
        "sat_alt_km", "slant_range_km"
    ]
    
    try:
        data_resp = get_series_data(job_id, fields=fields_needed, max_points=1000)
    except Exception as e:
        print(f"数据提取失败，请检查 job_id 是否正确: {e}")
        return

    time = data_resp["time"]
    series = data_resp["series"]

    # ==========================================
    # 2. 开始使用 Matplotlib 绘制 2x2 面板
    # ==========================================
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"AtmosOrbitSim V4.0 后端数据打样 (Job: {job_id})", fontsize=18, fontweight='bold')

    # --- [左上] 图表 1：2D 星下点轨迹 ---
    ax1 = fig.add_subplot(221)
    ax1.set_title("1. 2D 地球覆盖轨迹图 (Ground Track)")
    # 为了演示高光，简单的散点图
    ax1.scatter(series["sat_lon"], series["sat_lat"], c='cyan', s=5, alpha=0.6)
    ax1.set_xlim(-180, 180)
    ax1.set_ylim(-90, 90)
    ax1.set_xlabel("经度 (Lon)")
    ax1.set_ylabel("纬度 (Lat)")
    ax1.grid(True, linestyle='--', alpha=0.5)

    # --- [右上] 图表 2：视场与光照分析 ---
    ax2 = fig.add_subplot(222)
    ax2.set_title("2. 载荷视场与光照分析面板")
    # 画面积图 (填充 min 和 max 之间的区域)
    ax2.fill_between(time, series["fov_alt_min_km"], series["fov_alt_max_km"], color='orange', alpha=0.3, label="视场覆盖带")
    ax2.plot(time, series["tangent_alt_km"], color='red', linewidth=2, label="靶心高度 (Tangent)")
    ax2.set_xlabel("时间 (s)")
    ax2.set_ylabel("高度 (km)")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    # --- [左下] 图表 3：姿态机动面板 ---
    ax3 = fig.add_subplot(223)
    ax3.set_title("3. 姿态机动与噪声控制面板 (YPR vs Noise)")
    
    # 1. 主 Y 轴：绘制宏观的姿态角
    line1 = ax3.plot(time, series["sat_roll_deg"], label="Roll (滚转)", color='tab:blue', linewidth=1.5)
    line2 = ax3.plot(time, series["sat_pitch_deg"], label="Pitch (俯仰)", color='tab:green', linewidth=1.5)
    line3 = ax3.plot(time, series["sat_yaw_deg"], label="Yaw (偏航)", color='tab:purple', linewidth=1.5)
    
    ax3.set_xlabel("时间 (s)")
    ax3.set_ylabel("姿态角度 (Deg)")
    ax3.grid(True, alpha=0.3)

    # 2. 副 Y 轴：绘制微观的高频抖动噪声
    ax3_twin = ax3.twinx()
    line4 = ax3_twin.plot(time, series["attitude_noise_deg"], label="Noise (噪声)", 
                          color='tab:gray', alpha=0.6, linewidth=1.0)
    
    # 将副 Y 轴的文字和刻度标为灰色，从视觉上区分开
    ax3_twin.set_ylabel("微观噪声波动 (Deg)", color='tab:gray')
    ax3_twin.tick_params(axis='y', labelcolor='tab:gray')
    
    # 3. 优雅地合并两个 Y 轴的图例 (Legend)
    lines = line1 + line2 + line3 + line4
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, loc="upper right")

    # --- [右下] 图表 4：轨道与测距 (双 Y 轴) ---
    ax4 = fig.add_subplot(224)
    ax4.set_title("4. 轨道衰减与目标测距面板")
    color1 = 'tab:blue'
    ax4.set_xlabel("时间 (s)")
    ax4.set_ylabel("卫星高度 (km)", color=color1)
    ax4.plot(time, series["sat_alt_km"], color=color1, label="Sat Alt")
    ax4.tick_params(axis='y', labelcolor=color1)

    ax4_twin = ax4.twinx()  # 实例化共享 x 轴的第二个 y 轴
    color2 = 'tab:red'
    ax4_twin.set_ylabel("目标斜距 (km)", color=color2)
    ax4_twin.plot(time, series["slant_range_km"], color=color2, linestyle='--', label="Slant Range")
    ax4_twin.tick_params(axis='y', labelcolor=color2)
    
    fig.tight_layout(rect=[0, 0.03, 1, 0.95]) # 调整布局防重叠
    
    # 3. 保存图片并展示
    save_path = f"output/{job_id}_mockup.png"
    plt.savefig(save_path, dpi=150)
    print(f"打样图片已生成并保存至: {save_path}")
    plt.show()

if __name__ == "__main__":
    test_job_id = "job_06c37e69" 
    
    plot_dashboard_mockup(test_job_id)