# agri-field-designer

农机作业智能规划系统 - 包含路径规划、轨迹分析、机器人规划等多个模块

## 项目结构

```
agri-field-designer/
├── agri_planner_interactive.html    # 交互式路径规划工具（Leaflet地图）
├── rtk_agri_analysis/              # RTK轨迹分析模块
│   ├── data/gps_trace.json         # GPS轨迹数据
│   ├── core.py                     # 数据处理核心（坐标转换、异常检测）
│   ├── visualize.py                # Folium地图可视化
│   ├── report.py                   # Markdown报告生成
│   ├── main.py                     # 程序入口
│   └── output/                     # 输出目录
├── agri_machinery_path_planner.py  # 农机路径规划核心算法
├── smart_irrigation_planner.py     # 智能灌溉规划
├── smart_sowing_planner.py         # 智能播种规划
├── harvesting_robot_planner.py      # 收获机器人规划
├── fruit_maturity_detector.py      # 水果成熟度检测
├── plot_harvest_viz.py            # 收获可视化
├── real_data_interface.py         # 真实数据接口
├── test_end_to_end.py             # 端到端测试
├── requirements.txt               # Python依赖
└── whitepaper.md                  # 技术白皮书
```

## 技术栈

- **Python 3** - 核心算法开发
- **numpy, pandas** - 数据处理
- **folium** - 交互式地图生成
- **Leaflet.js** - 前端地图渲染
- **OpenStreetMap / Esri** - 底图服务

## 功能模块

### 1. 交互式路径规划 (agri_planner_interactive.html)

基于 Leaflet 地图的农机作业路径规划工具，支持任意多边形田块绘制与弓字形路径自动生成。

**功能特点**：
- 🗺️ 交互式地图绘制 - 在卫星图/街道图上自由绘制
- 🔷 多边形支持 - 凸多边形、凹多边形、L形等任意形状
- 📐 弓字形路径 - 自动生成贴合边界的作业路径
- 📊 作业统计 - 自动计算面积、路径长度、预计时间
- 💾 数据导出 - 支持 GeoJSON 格式导出

**操作流程**：
1. 点击 **✏️ 画田块** 进入绘制模式
2. 在地图上依次点击田块边界顶点
3. 点击 **✅ 完成绘制** 结束绘制
4. 设置作业幅宽和速度
5. 点击 **▶️ 生成作业路径** 生成规划路径

### 2. RTK轨迹分析 (rtk_agri_analysis/)

对农机作业RTK轨迹数据进行深度分析，检测异常、评估作业质量。

**功能特点**：
- 📍 GPS轨迹数据加载与清洗
- ⚡ 速度异常检测
- 🔍 漏喷/重叠栅格分析
- 🗺️ Folium交互式地图可视化
- 📄 Markdown质量报告自动生成

**使用方式**：
```bash
cd rtk_agri_analysis
pip install -r requirements.txt
python main.py
```

### 3. 核心算法模块

| 模块 | 功能说明 |
|------|----------|
| `agri_machinery_path_planner.py` | 农机路径规划核心算法（弓字形、D* Lite避障、B样条平滑） |
| `smart_irrigation_planner.py` | 智能灌溉规划 |
| `smart_sowing_planner.py` | 智能播种规划 |
| `harvesting_robot_planner.py` | 收获机器人路径规划 |
| `fruit_maturity_detector.py` | 水果成熟度视觉检测 |

## 快速开始

### 环境配置

```bash
# 克隆仓库
git clone https://github.com/AWTX550W/agri-field-designer.git
cd agri-field-designer

# 安装Python依赖
pip install -r requirements.txt
```

### 运行RTK轨迹分析

```bash
cd rtk_agri_analysis
python main.py
# 输出：交互式地图 HTML 文件和分析报告
```

### 使用交互式路径规划

直接在浏览器中打开 `agri_planner_interactive.html` 即可使用，无需安装任何依赖。

## 算法说明

### 弓字形路径生成（扫描线算法）

1. 沿纬度方向等间距生成水平扫描线
2. 求扫描线与多边形边界的交点
3. 交点配对形成作业段
4. 相邻作业段交替方向，形成弓字形

### 速度异常检测

基于滑动窗口的速度统计，识别急加速、急减速、停滞等异常情况。

## 适用场景

- 🌾 农田作业路径规划
- 🚜 农机自动驾驶演示
- 📡 RTK轨迹质量分析
- 🤖 农业机器人路径规划

## License

MIT License
