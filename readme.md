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
atmos_orbit_sim/
├── configs/                    # 任务配置中心 (存放所有 JSON 测试用例)
├── data/                       # 物理基准数据 (需放置 orekit-data.zip)
├── output/                     # 仿真数据落盘区 (Parquet 结果文件)
├── core/                       # 核心物理引擎源码
│   ├── attitude_controller.py  # 姿态状态机与噪声发生器
│   ├── geodesy_engine.py       # WGS84 椭球靶心求交引擎
│   ├── optics_simulator.py     # 载荷光电映射与光行差模型
│   ├── orekit_generator.py     # 摄动力封装与底层轨道生成
│   └── simulation_engine.py    # 顶层状态机与生命周期管理
├── services/                   # 业务逻辑与数据服务层
│   ├── simulation_service.py   # 异步任务调度与清理策略
│   ├── result_service.py       # Parquet 数据读写接口
│   └── export_service.py       # 数据导出 (CSV/Excel)
├── utils_io/                   # I/O 工具
│   ├── config_loader.py        # JSON 配置加载
│   └── parquet_writer.py       # Parquet 高效写入
├── scripts/                    # 辅助脚本
│   ├── plot_mockup.py          # 数据可视化
│   └── cleanup_parquet.py      # Parquet 文件清理工具
├── gui_ultimate.py             # PyQt5 交互式仪表板（推荐启动方式）
├── gui_main.py                 # 备用 GUI 入口
├── main.py                     # CLI 仿真入口
├── docs/
│   └── api_spec.md             # 前端工程师 API 规范
└── readme.md                   # 项目说明文档
```

---

## 快速启动 (Quick Start)

### 1. 环境准备

项目依赖 Python 科学计算栈与 Orekit Python 包装器：

```bash
# 推荐使用 Python 3.8+
pip install pandas pyarrow scipy matplotlib pyqt5

# Orekit 安装建议：
# 1) Windows 强烈建议用 conda（Java 依赖更稳定）
conda install -c conda-forge orekit

# 2) pip 仅作为可选方案（在部分 Windows 环境可能失败）
# pip install orekit
```

### 2. 挂载物理星历数据

* 前往 [Orekit 官方网站](https://www.orekit.org/) 下载最新的 `orekit-data.zip`
* 放置到项目目录：

```
data/orekit-data.zip
```

### 3. 启动仿真 GUI（推荐）

```bash
cd atmos_orbit_sim
python gui_ultimate.py
```

在 GUI 中：
- 选择或创建仿真配置（轨道参数、传播模型等）
- 实时查看推演进度与仪表板（4 个子图：地面轨迹、FOV/高度、姿态/噪声、轨道参数）
- 鼠标 hover 查看切点与卫星详细数据
- 导出结果为 Parquet 或 CSV

### 4. 命令行执行（可选）

```bash
python main.py --config configs/config_tc01_dynamic_side.json
```

### 5. 清理输出文件（可选）

自动保留最近 3 个 parquet 文件；手动清理：

```bash
python scripts/cleanup_parquet.py --n 3
```

---

## 数据输出字典 (Data Schema)

仿真结束后，在 `output/` 目录生成 `.parquet` 文件（Parquet 列式格式，压缩存储），字段如下：

| 字段名                  | 类型      | 说明                          |
| --------------------- | ------- | ----------------------------- |
| **时间**                |         |                               |
| time_sec              | Float   | 仿真时间（秒）                  |
| **卫星位置 & 高度**      |         |                               |
| sat_x / y / z         | Float   | 卫星在 WGS84 ITRF 系下的绝对三维坐标（米） |
| sat_lat / lon         | Float   | 星下点 WGS84 经纬度（度）      |
| sat_alt_km            | Float   | 卫星轨道高度（公里）           |
| **卫星姿态**            |         |                               |
| sat_roll_deg          | Float   | 滚转角（Roll，绕速度轴，度）   |
| sat_pitch_deg         | Float   | 俯仰角（Pitch，绕横轴，度）    |
| sat_yaw_deg           | Float   | 偏航角（Yaw，绕竖轴，度）      |
| attitude_noise_deg    | Float   | 实时叠加的姿态噪声（热漂+抖动，度） |
| **临边切点**            |         |                               |
| tangent_lat / lon     | Float   | 临边切点 WGS84 经纬度（度）    |
| tangent_alt_km        | Float   | 临边切点高度（公里）           |
| **光学与距离**          |         |                               |
| slant_range_km        | Float   | 卫星至切点斜距（公里）         |
| fov_alt_min_km        | Float   | 视场下边界高度（公里）*标准化值* |
| fov_alt_max_km        | Float   | 视场上边界高度（公里）*标准化值* |
| **地影状态**            |         |                               |
| sat_in_eclipse        | Boolean | 卫星是否处于地影（True=阴影）  |
| tangent_in_eclipse    | Boolean | 临边切点是否处于地影           |

**备注**：
- `fov_alt_min_km` 和 `fov_alt_max_km` 在生产端已自动排序 (min ≤ max)，GUI 前端无需额外交换。
- 地影状态由太阳-地球-卫星几何关系精确计算。
- Parquet 文件启用 snappy 压缩，相比 CSV 缩减 ~70%。

---

## 配置文件规范 (Config File Format)

所有配置文件放在 `configs/` 目录，JSON 格式。README 只保留最常用的结构，完整字段说明以 `docs/api_spec.md` 为准。

### 典型结构

```json
{
  "orbit_propagation": {
    "model": "HPOP",
    "epoch_iso": "2026-05-06T00:00:00Z",
    "duration_sec": 3600,
    "step_sec": 10,
    "a": 6878137.0,
    "e": 0.001,
    "i": 97.5,
    "raan": 0.0,
    "arg_pe": 0.0,
    "m0": 0.0,
    "cd": 2.5,
    "cr": 1.2,
    "perturbations": {
      "gravity_degree": 10,
      "gravity_order": 10,
      "enable_thirdbody": true,
      "enable_drag": true,
      "enable_srp": true
    }
  },
  "payload_optics": {
    "fov_deg": 1.2,
    "mounting_angles": {
      "mount_roll_deg": 68.0,
      "mount_pitch_deg": 0.0,
      "mount_yaw_deg": 0.0
    }
  },
  "attitude_control": {
    "mode": "DYNAMIC",
    "target_alt_km": 400,
    "locked_angle_deg": null,
    "perturbations": {
      "enable_noise": true,
      "drift_rate_arcsec_s": 0.1,
      "jitter_3sigma_arcsec": 1.0
    }
  }
}
```

### 说明

- 轨道角度字段默认按“度”传入，后端统一转弧度。
- `a` 使用米，`i` / `raan` / `arg_pe` / `m0` 使用度。
- `HPOP` 使用 `gravity_degree` / `gravity_order`，`ANALYTICAL` 仅用 `gravity_degree`。
- `payload_optics` 支持 `fov_deg`，也保留焦距/传感器模式字段用于扩展。
- `attitude_control` 中 `mode` 取 `DYNAMIC` 或 `LOCKED`，目标高度用 `target_alt_km`。

---

## 故障排查 (Troubleshooting)

| 问题 | 症状 | 解决方案 |
| --- | --- | --- |
| 导入 orekit 失败 | `ImportError: No module named 'orekit'` | `pip install orekit` 或 `conda install -c conda-forge orekit` |
| 星历数据缺失 | `orekit.errors.OrekitException: Orekit data not found` | 确保 `data/orekit-data.zip` 存在且路径正确 |
| GUI 中文乱码 | 汉字显示为方块或符号 | 已内置 FontProperties 处理；若仍有问题，更新 matplotlib（`pip install --upgrade matplotlib`） |
| 仿真卡顿 | GUI 无响应 | 仿真在后台线程运行；若进度条长时间不动，检查 CPU/内存占用 |
| Parquet 文件过多 | `output/` 占用空间过大 | 运行 `python scripts/cleanup_parquet.py --n 3` 保留最近 3 个 |

---

## 开发指南 (Developer Guide)

### 核心模块说明

- **`core/simulation_engine.py`**：主仿真引擎，负责推演循环与数据写入；每次运行前自动清理旧 parquet 文件（保留最近 N 个）。
- **`core/orekit_generator.py`**：Orekit Java 对象生成，支持多种传播模型（HPOP/SGP4/ANALYTICAL/TWOBODY）。
- **`core/optics_simulator.py`**：光学映射、视场计算、光行差补偿。
- **`core/attitude_controller.py`**：动态姿态控制与噪声注入（热漂、抖动）。
- **`core/geodesy_engine.py`**：WGS84 椭球体计算、切点求解、斜距计算。
- **`services/simulation_service.py`**：异步任务调度、job 状态管理、parquet 清理策略。
- **`services/result_service.py`**：Parquet 数据读取与字段提取。

---
