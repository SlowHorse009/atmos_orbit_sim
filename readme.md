# 🛰️ AtmosOrbitSim (V4.0)

**高保真临边大气探测轨道与光学几何仿真引擎 (High-Fidelity Limb Sounding Orbit & Optics Simulation Engine)**

AtmosOrbitSim 是一个基于 Python 封装 Orekit 底层核心的工业级航天动力学仿真框架。专为低轨 (LEO) 至大椭圆轨道 (HEO) 的卫星临边大气探测任务设计，实现了从星历推演、真实地球椭球体靶心求交，到微观光行差与高频姿态抖动补偿的全链路闭环仿真。

---

## 核心特性 (Core Features)

### 全能轨道传播器 (Multi-Model Orbit Propagation)

* **HPOP (高精度数值积分)**
  支持自定义高阶重力场 (J21x21)、日月第三体引力、高保真大气阻力 (NRLMSISE00) 与太阳光压 (SRP) 模型。

* **SGP4 (经验解析)**
  原生支持解析北美防空司令部 (NORAD) 的两行轨道根数 (TLE)，用于真实在轨空间目标的实战观测与推演。

* **ANALYTICAL (快速解析)**
  基于 Brouwer-Lyddane 理论，完美支持长期（如数月、数年）轨道演化的极速推演。

* **TWOBODY (理想双体)**
  纯粹的开普勒模型，用于算法基准校验 (Baseline)。

---

### WGS84 严密几何求交 (Geodesy Engine)

* 摒弃简单的“球体地球”假设，采用精确的 WGS84 参考椭球体。
* 运用 Brent 寻优算法，严密求解空间视线 (LOS) 与大气层的临边切点、绝对斜距及地平线边界条件。

---

### 动态光学与姿态控制 (Attitude & Optics Kinematics)

* **自适应目标追踪**
  无论是在圆轨道还是高度剧变的大椭圆轨道 (HEO)，控制器均能动态机动主控轴 (Roll/Pitch)，锁定目标探测高度（如 400km）。

* **真实物理噪声注入**
  引擎可自适应当前物理轨道周期，动态注入低频热弹性漂移与高频飞轮微振动 (Jitter)。

* **相对论光行差补偿 (Velocity Aberration)**
  精确计算高速运动带来的光子表观来向偏差。

---

### 极致 I/O 与动态调度 (Data Engineering)

* 使用 Apache Parquet 列式存储格式与 `pyarrow` 引擎，实现海量遥测数据的高效压缩与快速读写。
* 支持 Job ID 动态路由，通过读取 `configs/` 目录下 JSON 任务流自动生成沙盒化结果文件。

---

## 目录架构 (Architecture)

```text
ATMOS_ORBIT_SIM/
├── configs/                # 任务配置中心 (存放所有 JSON 测试用例)
├── data/                   # 物理基准数据 (需放置 orekit-data.zip)
├── output/                 # 仿真数据落盘区 (Parquet 结果文件)
├── src/                    # 核心物理引擎源码
│   ├── attitude_controller.py  # 姿态状态机与噪声发生器
│   ├── geodesy_engine.py       # WGS84 椭球靶心求交引擎
│   ├── optics_simulator.py     # 载荷光电映射与光行差模型
│   ├── orekit_generator.py     # 摄动力封装与底层轨道生成
│   └── simulation_engine.py    # 顶层状态机与生命周期管理
├── run_sim.py              # 仿真任务调度入口脚本
├── plot_results.py         # 遥测数据高保真可视化脚本
├── .gitignore              # Git 过滤规则
└── readme.md               # 项目说明文档
```

---

## 快速启动 (Quick Start)

### 1. 环境准备

项目依赖 Python 科学计算栈与 Orekit Python 包装器：

```bash
# 推荐使用 Conda 虚拟环境
pip install pandas pyarrow scipy matplotlib

# 确保已通过 conda 或 pip 正确安装 orekit
```

---

### 2. 挂载物理星历数据

* 前往 Orekit 官方网站下载最新的 `orekit-data.zip`
* 放置到项目目录：

```text
data/orekit-data.zip
```

---

### 3. 执行仿真推演

```bash
python run_sim.py
```

---

## 数据输出字典 (Data Schema)

仿真结束后，在 `output/` 目录生成 `.parquet` 文件，字段如下：

| 字段名                | 类型      | 说明               |
| ------------------ | ------- | ---------------- |
| time_sec           | Float   | 仿真时间（秒）          |
| sat_x / y / z      | Float   | J2000 惯性系三维坐标（米） |
| sat_lat / lon      | Float   | 星下点 WGS84 经纬度（度） |
| sat_alt_km         | Float   | 卫星轨道高度（公里）       |
| sat_roll_deg       | Float   | 滚转角（主控轴）         |
| sat_pitch_deg      | Float   | 俯仰角（次控轴）         |
| sat_yaw_deg        | Float   | 偏航角（像旋补偿）        |
| attitude_noise_deg | Float   | 姿态噪声（度）          |
| tangent_lat / lon  | Float   | 临边切点经纬度          |
| tangent_alt_km     | Float   | 临边切点高度（核心目标）     |
| slant_range_km     | Float   | 卫星至切点斜距          |
| fov_alt_min_km     | Float   | 视场下边界高度          |
| fov_alt_max_km     | Float   | 视场上边界高度（深空为 NaN） |
| in_eclipse         | Boolean | 是否处于地影           |

---
