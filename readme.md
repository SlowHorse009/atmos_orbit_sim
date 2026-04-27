# 🌍 AtmosOrbitSim: 卫星中高层大气临边探测全链路仿真系统

## 📝 项目简介
本项目是一个高精度的航天系统级仿真框架，专为 **中高层大气临边探测（Limb Sounding）** 任务设计。  

系统融合了：
- 轨道动力学（SGP4）
- 三维侧扫高精度几何解算
- 闭环动态姿态跟瞄
- NRLMSISE-00 空间物理环境模型  

实现了从**卫星平台 → 观测几何 → 大气切点 → 环境参数**的全链路数据推演。

---

## ✨ 核心特性

### 🔁 动态闭环姿态跟瞄 (Dynamic Pitch Control)
突破传统固定俯仰角设计，根据卫星真实轨道高度波动，实时计算并自适应调整下俯角 $\alpha$，确保视场最下边缘锁定在绝对安全高度（如 20 km），规避地表强光干扰。

---

### 📐 高精度光程与几何解算
弃用传统“地表切点”近似，采用真实目标高度几何模型：

$$
(R_e + H_t)^2 + (L/2)^2 = (R_e + H_t + \Delta h)^2
$$

确保在大天顶角条件下，大气分层光程（Path Length）计算具有高物理精度。

---

### 🌌 微观物理环境感知
内置 NRLMSISE-00 大气模型，可自动解算：

- 卫星本体环境（用于原子氧剥蚀评估）
- 视线切点环境（用于气辉反演）

输出参数包括：
- 温度
- 压强
- 多组分数密度

---

### 📷 4K级光学传感器映射
精确模拟 GSENSE4040 + 100mm 光学系统：

- 分辨率：$4096 \times 4096$
- 像元与大气垂直高度一一映射

---

## 📂 项目结构

```text
atmos_orbit_sim/
├── src/
│   ├── geometry.py     # 高精度 3D 侧向切点解算与光程计算
│   ├── sensor.py       # GSENSE4040 光学传感器参数与 FOV 映射模型
│   └── atmosphere.py   # NRLMSISE-00 物理环境解算与状态方程推导
├── notebooks/
│   ├── 01_fov_analysis.ipynb      # 视场角与安全下俯角验证
│   ├── 02_orbit_propagation.ipynb # 轨道外推测试
│   ├── 03_full_pipeline.ipynb     # 全链路仿真
│   └── 04_visualization.ipynb     # 3D 可视化 (Plotly)
├── integrated_mission_data.csv    # 全链路任务数据输出
└── README.md
```

---

## 📐 核心算法与坐标系转换矩阵

系统精度的核心在于严密的坐标变换链条：

---

### 1️⃣ 轨道历元解析 (TLE → TEME)

使用 SGP4 解析 TLE，得到：

- 卫星位置 $\vec{R}$
- 卫星速度 $\vec{V}$  

坐标系：TEME（惯性系）

---

### 2️⃣ 地球自转补偿 (TEME → ITRS / ECEF)

引入 IERS 参数，转换为地固坐标系：

- 位置向量：
  $$
  \vec{R}_{ecef} = [X, Y, Z]
  $$
- 速度向量：
  $$
  \vec{V}_{ecef} = [V_x, V_y, V_z]
  $$

---

### 3️⃣ 构建局部轨道坐标系

在卫星质心建立正交基：

- **天底向量 (Nadir)**  
  $$
  \vec{U}_{nadir} = -\frac{\vec{R}}{|\vec{R}|}
  $$

- **沿轨向量 (Along-track)**  
  $$
  \vec{V}_{horiz} = \vec{V} - (\vec{V} \cdot \vec{U}_{nadir})\vec{U}_{nadir}
  $$
  $$
  \vec{U}_{along} = \frac{\vec{V}_{horiz}}{|\vec{V}_{horiz}|}
  $$

- **侧向向量 (Cross-track)**  
  $$
  \vec{U}_{cross} = \vec{U}_{along} \times \vec{U}_{nadir}
  $$

---

### 4️⃣ 视线矢量与切点投影

#### 视线方向（LOS）

$$
\vec{U}_{los} = \cos(\alpha)\vec{U}_{cross} + \sin(\alpha)\vec{U}_{nadir}
$$

---

#### 切点距离

$$
D_{tangent} = -\vec{R} \cdot \vec{U}_{los}
$$

---

#### 切点位置

$$
\vec{P}_{tangent} = \vec{R} + D_{tangent}\vec{U}_{los}
$$

---

最终输出：
- 经度
- 纬度
- 切点高度 $H_t$

---

## 🚀 快速开始

### 🧩 环境依赖

```bash
pip install numpy pandas astropy sgp4 nrlmsise00 plotly
```

---

### ▶️ 运行流程

#### 1. 全链路仿真

运行：

```
notebooks/03_full_pipeline.ipynb
```

输出：
- `integrated_mission_data.csv`

---

#### 2. 可视化

运行：

```
notebooks/04_visualization.ipynb
```

功能：
- 3D 地球
- 卫星轨迹
- 探测足迹热力图

---

## 📊 数据输出说明

| 字段名称 | 单位 | 描述 |
|----------|------|------|
| Sat_Alt_km | km | 卫星实时轨道高度 |
| Pitch_Deg | ° | 动态下俯角 |
| Sat_Temp_K | K | 卫星环境温度 |
| Target_Alt_km | km | 切点高度 |
| Target_Press_Pa | Pa | 切点气压 |
| Target_Temp_K | K | 切点温度 |

---

## 🎯 项目目标

构建一个用于：

- 高精度临边探测任务设计  
- 气辉反演算法验证  
- 卫星载荷性能评估  

的**工程级仿真平台**

---

**Developed for High-Precision Limb Sounding Mission Simulation 🚀**