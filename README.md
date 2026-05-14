# agri-field-designer

农机作业智能规划系统 - 包含路径规划、轨迹分析、机器人规划等多个模块

## 项目结构

```
agri-field-designer/
├── agri_planner_interactive.html    # 交互式路径规划工具（Leaflet地图）
├── rtk_agri_analysis/               # RTK轨迹分析模块
│   ├── data/gps_trace.json
│   ├── core.py                      # 数据处理核心
│   ├── visualize.py                 # Folium地图可视化
│   ├── report.py                    # Markdown报告生成
│   ├── main.py                      # 程序入口
│   └── output/
├── agri_machinery_path_planner.py   # 农机路径规划核心算法
├── smart_irrigation_planner.py      # 智能灌溉规划
├── smart_sowing_planner.py          # 智能播种规划
├── harvesting_robot_planner.py      # 收获机器人规划
├── fruit_maturity_detector.py       # 水果成熟度检测
├── plot_harvest_viz.py              # 收获可视化
├── real_data_interface.py           # 真实数据接口
├── test_end_to_end.py               # 端到端测试
├── requirements.txt                 # 依赖
└── whitepaper.md                    # 技术白皮书
```

## 技术栈

- Python 3, numpy, pandas, folium
- Leaflet.js, OpenStreetMap, Esri卫星图
- GPS/RTK轨迹处理

## 功能模块

### 1. 交互式路径规划 (agri_planner_interactive.html)
- 基于Leaflet地图的田块绘制
- 支持任意多边形形状
- 弓字形路径自动生成

### 2. RTK轨迹分析 (rtk_agri_analysis/)
- GPS轨迹数据加载与清洗
- 速度异常检测
- 漏喷/重叠分析
- Folium交互地图
- Markdown质量报告

### 3. 核心算法模块
- `agri_machinery_path_planner.py` - 农机路径规划
- `smart_irrigation_planner.py` - 灌溉规划
- `smart_sowing_planner.py` - 播种规划
- `harvesting_robot_planner.py` - 收获机器人

## 快速使用

```bash
# RTK轨迹分析
cd rtk_agri_analysis
python main.py

# 农机路径规划
python agri_machinery_path_planner.py
```

## License

MIT
