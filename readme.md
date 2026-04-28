# 🛰️ Satellite Limb Observation Digital Twin (SLODT)

### 基于 Orekit 与 WGS84 的临边大气探测高保真数字孪生系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Orekit 12.x](https://img.shields.io/badge/Engine-Orekit_12.x-orange.svg)](https://www.orekit.org/)
[![Geodesy-WGS84](https://img.shields.io/badge/Geodesy-WGS84-green.svg)](#)

---

## 📖 项目简介

本项目是一个专门为**临边大气探测卫星（Limb Sounder）**设计的工业级全链路仿真平台。系统集成了高精度轨道动力学、严密的 WGS84 椭球体几何、动态姿态补偿算法以及三维矢量光学映射，能够精准模拟 600km 轨道卫星对 60km–150km 大气层的观测全过程。

### 核心痛点解决

* **地球扁率修正**：彻底抛弃圆球体模型，采用 WGS84 椭球体解算，消除极地与赤道间高达 21km 的切点高度系统误差。
* **硬件动态补偿**：内置补偿镜（Scanning Mirror）控制逻辑，自动吸收因轨道高度起伏带来的指向偏差。
* **物理微振动模拟**：集成角秒级高频抖动（Jitter）与低频热漂移（Drift）模型，支撑精细化图像像质评估。

---

## 🛠️ 环境配置

建议使用 Conda 管理环境以确保 Java 桥接库（JCC）的稳定性。

```bash
# 创建环境
conda create -n orbit_env python=3.10
conda activate orbit_env

# 安装核心依赖
pip install orekit
pip install numpy pandas
pip install pyproj
```

---

## 📂 模块架构

```plaintext
atmos_orbit_sim/
├── src/
│   ├── orekit_generator.py   # 轨道动力学内核（支持 HPOP/数值积分）
│   ├── geodesy_engine.py     # WGS84 大地测量与 3D 射线求交引擎
│   ├── attitude_control.py   # 具备局部曲率感知的动态姿态控制器
│   └── sensor_optics.py      # 三维矢量光学映射与 FOV 覆盖解算
├── notebook/
│   └── full_chain_sim.ipynb  # 全链路飞行推演集成示例
└── README.md
```

---

## 🚀 核心功能说明

### 1. 轨道动力学 (orekit_generator)

基于 ESA Orekit 实现。支持 HPOP（High-Precision Orbit Propagator），默认搭载 6×6 阶地球重力场模型，真实还原卫星在不均匀重力场中的“高度起伏”。

### 2. WGS84 大地测量 (geodesy_engine)

采用 ReferenceEllipsoid.getWgs84 模型。核心算法 `get_limb_tangent_lla` 通过 3D 向量投影法，在椭球面上寻找最严密的视线切点位置，输出切点经纬度。

### 3. 动态姿态控制 (attitude_control)

模拟卫星“粗精复合指向”策略：

* 粗指向：卫星本体预倾斜安装（如 68°）
* 精补偿：根据当前纬度下的局部地球半径，实时计算补偿镜偏移角，死死咬住目标大气层高度

### 4. 矢量光学模拟 (sensor_optics)

摒弃传统的二维三角函数，采用 Vector3D 空间矢量运算。支持通过 FOV 或 焦距/靶面尺寸 双驱动初始化，输出最真实的大气探测高度覆盖范围。

---

## 📊 快速使用示例

```python
from orekit_generator import OrekitOrbitGenerator
from geodesy_engine import WGS84GeodesyEngine
from attitude_control import DynamicAttitudeController
from sensor_optics import LimbOpticsSimulator

# 1. 启动引擎并生成轨道
orbit_sys = OrekitOrbitGenerator(prop_model='HPOP', a=6978137.0, e=0.001)
df = orbit_sys.generate_ephemeris_dataframe(duration_sec=180)

# 2. 初始化大地测量与光学
geodesy = WGS84GeodesyEngine()
optics = LimbOpticsSimulator(focal_length_mm=850.0, sensor_size_mm=32.5)

# 3. 执行单点观测计算
# 详情参考 notebook/full_chain_sim.ipynb
```

---

## 📝 开发者备注

* **JVM 初始化**：本项目依赖 Java 虚拟机，运行前必须确保执行了 `orekit.initVM()`
* **坐标系一致性**：所有计算均在 ECEF（地固坐标系）下进行，以确保与遥感后处理流程无缝对接
* **Git 提交注意**：本项目已移除旧的 nbstripout 过滤器，提交时请确保 `.ipynb` 文件的版本整洁
