# agri-field-designer

农机作业路径规划与轨迹分析工具集

## 项目结构

```
agri-field-designer/
├── agri_planner_interactive.html    # 交互式路径规划工具（Leaflet地图）
└── rtk_agri_analysis/               # RTK轨迹分析模块
    ├── data/
    │   └── gps_trace.json          # GPS轨迹数据
    ├── core.py                      # 数据处理核心（坐标转换、异常检测）
    ├── visualize.py                 # Folium交互地图生成
    ├── report.py                    # Markdown分析报告生成
    ├── main.py                      # 程序入口
    └── output/                      # 输出目录
```

## 模块说明

### rtk_agri_analysis - RTK轨迹分析

**技术栈**: Python 3, numpy, pandas, folium, json

**功能**:
- GPS轨迹数据加载与清洗
- WGS84坐标系转换
- 速度异常检测
- 漏喷/重叠栅格分析
- Folium交互式地图可视化
- Markdown作业质量报告自动生成

**快速使用**:
```bash
cd rtk_agri_analysis
python main.py
```

### agri_planner_interactive.html

基于 Leaflet 地图的交互式农机作业路径规划工具，支持任意多边形田块绘制与弓字形路径自动生成。

直接用浏览器打开即可使用。

## License

MIT
