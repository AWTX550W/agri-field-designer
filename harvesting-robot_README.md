# 🌾 采摘机器人模块

> 农业智能机器人核心算法集 - 从播种到采摘的全流程自动化

## 📖 项目简介

本模块是 OpenClaw 农业自动化系统的核心算法集，专注于果蔬采摘场景的智能化解决方案。通过 AI 视觉识别、路径规划和传感器融合，实现采摘机器人的自主作业。

## 🏗️ 模块结构

```
harvesting-robot/
├── harvesting_robot_planner.py    # 采摘路径规划器 + 农民路径预测
├── fruit_maturity_detector.py     # 果实成熟度检测 (HSV颜色分析)
├── smart_sowing_planner.py        # 智能播种规划
├── smart_irrigation_planner.py    # 智能灌溉规划 ⭐NEW
├── real_data_interface.py         # 传感器与GPS数据接口
├── gps_trace.json                 # GPS轨迹测试数据
└── README.md                      # 本文档
```

## 🚀 快速开始

### 环境要求
```bash
pip install opencv-python numpy
```

### 基本使用

```python
from harvesting_robot_planner import HarvestingRobotPlanner, FruitTarget

# 创建规划器
planner = HarvestingRobotPlanner()

# 添加果实目标
targets = [
    FruitTarget(x=1.2, y=0.5, z=1.8, radius=0.04, maturity=0.85),
]

# 规划采摘路径
path = planner.plan_path(targets)
```

## 📦 核心模块

| 模块 | 功能 | 依赖 |
|------|------|------|
| `harvesting_robot_planner.py` | 采摘路径规划、农民避障 | NumPy |
| `fruit_maturity_detector.py` | 果实成熟度检测 | OpenCV, NumPy |
| `smart_sowing_planner.py` | 播种密度优化 | NumPy |
| `smart_irrigation_planner.py` | 精准灌溉规划 | NumPy |
| `real_data_interface.py` | GPS/摄像头/传感器接口 | OpenCV, NumPy |

## 🎯 主要功能

### 1. 采摘路径规划
- 最近邻优先算法
- 贪心路径优化
- 机械臂运动学约束

### 2. 农民作业预测
- GPS轨迹分析
- 线性回归预测
- 碰撞风险检测

### 3. 成熟度检测
- HSV颜色空间分析
- 红/绿比例计算
- 实时视频流处理

### 4. 播种优化
- 密度计算
- 行距/株距优化
- 作物参数数据库

### 5. 智能灌溉 ⭐NEW
- 土壤湿度分析
- 天气预报整合
- 作物需水量计算
- 灌溉方案生成
- 水资源优化分配

## 🌊 智能灌溉模块详解

```python
from smart_irrigation_planner import (
    SmartIrrigationPlanner, SoilData, SoilType,
    WeatherForecast, WeatherCondition, CropWaterNeed
)

# 创建规划器
planner = SmartIrrigationPlanner()

# 设置土壤数据
soil = SoilData(
    moisture=0.25,        # 湿度 0-1
    temperature=25.0,    # 温度 °C
    soil_type=SoilType.LOAMY,  # 土壤类型
    depth=0.3,           # 测量深度 m
    location="1号田"
)

# 设置天气预报
forecast = WeatherForecast(
    date=datetime.now(),
    condition=WeatherCondition.SUNNY,
    temperature_high=32,
    temperature_low=24,
    humidity=0.5,
    precipitation=0,
    wind_speed=2,
    uv_index=8
)

# 设置作物
corn = planner.calculate_crop_water_need("corn", 100, "tasseling")
tomato = planner.calculate_crop_water_need("tomato", 200, "fruiting")

# 生成灌溉方案
plan = planner.generate_irrigation_plan(
    soil=soil,
    crops=[corn, tomato],
    forecasts=[forecast],
    field_area=500,
    flow_rate=500
)

print(f"建议灌溉量: {plan.total_water}L")
print(f"灌溉时长: {plan.duration}分钟")
```

### 灌溉模块特性

| 功能 | 描述 |
|------|------|
| 土壤分析 | 湿度状态评估、灌溉建议 |
| 作物需水 | 内置番茄/玉米/小麦/草莓/黄瓜数据库 |
| 天气调整 | 温度、降水、湿度、风速综合计算 |
| 灌溉计划 | 7天灌溉日历、避开雨天 |
| 资源优化 | 水资源不足时的优先级分配 |

## 📊 技术指标

- 支持作物: 番茄、玉米、小麦、草莓、黄瓜
- 土壤类型: 砂土、壤土、粘土、粉砂土
- GPS精度: ~1m (取决于设备)
- 路径规划速度: <10ms (10个目标)
- 成熟度检测准确率: >85%

## 🔗 相关项目

- [主仓库 README](../README.md) - 项目总览
- [A2HMarket 同步](../a2hmarket-sync/) - 订单数据同步
- [微信爬虫](../wechat-crawler/) - 数据采集

## 📄 许可证

MIT License - 详见 [../../LICENSE](../../LICENSE)
