#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visualize.py — 农机作业轨迹 Folium 交互式地图可视化
输出：output/agri_work_map.html
内容：GPS 轨迹线、速度异常红点/黄点、作业覆盖热力图、图例
"""

import folium
import folium.plugins
import numpy as np
import pandas as pd
from typing import Dict, Any
import math


# ============================================================
# 1. 主地图生成函数
# ============================================================

def build_map(df: pd.DataFrame, coverage: Dict[str, Any],
              stats: Dict[str, Any], output_path: str = "output/agri_work_map.html"):
    """
    生成完整交互式地图并保存为 HTML
    图层说明：
    - 蓝色轨迹线 : 正常作业路径
    - 红色圆点   : 停机/超速跳点异常
    - 黄色圆点   : 加速度突变异常
    - 绿色矩形   : 作业田块边界
    - 热力图     : 覆盖密度分布
    """
    # 地图中心点
    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=18,
        tiles="OpenStreetMap"
    )

    # 卫星底图（需要互联网连接，若离线请注释掉此段）
    try:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="卫星影像",
            overlay=False,
            control=True
        ).add_to(m)
    except Exception:
        pass

    # ── 图层组 ──
    layer_track = folium.FeatureGroup(name="作业轨迹", show=True)
    layer_anomaly = folium.FeatureGroup(name="异常点", show=True)
    layer_field = folium.FeatureGroup(name="田块边界", show=True)
    layer_heatmap = folium.FeatureGroup(name="覆盖热力图", show=True)

    # ── 1. 田块边界矩形 ──
    _add_field_boundary(layer_field, df, coverage)

    # ── 2. 作业轨迹线（按正常/异常分段着色） ──
    _add_track_line(layer_track, df)

    # ── 3. 异常点标记 ──
    _add_anomaly_markers(layer_anomaly, df)

    # ── 4. 覆盖热力图（基于轨迹点密度） ──
    _add_heatmap(layer_heatmap, df, coverage)

    # ── 添加所有图层 ──
    layer_field.add_to(m)
    layer_track.add_to(m)
    layer_anomaly.add_to(m)
    layer_heatmap.add_to(m)

    # ── 5. 信息面板（左上角统计卡片） ──
    _add_info_panel(m, stats)

    # ── 6. 图例 ──
    _add_legend(m)

    # 图层控制
    folium.LayerControl(collapsed=False).add_to(m)

    # 保存
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    m.save(output_path)
    print(f"[地图] 已保存至 {output_path}")
    return m


# ============================================================
# 2. 内部辅助函数
# ============================================================

def _add_field_boundary(layer, df, coverage):
    """绘制田块边界矩形（基于覆盖分析范围反算经纬度）"""
    origin_lat = df["latitude"].iloc[0]
    origin_lon = df["longitude"].iloc[0]
    M_PER_LAT = 111320.0
    M_PER_LON = 111320.0 * math.cos(math.radians(origin_lat))

    def xy_to_latlon(x_m, y_m):
        return (origin_lat + y_m / M_PER_LAT,
                origin_lon + x_m / M_PER_LON)

    sw = xy_to_latlon(coverage["x_min"], coverage["y_min"])
    ne = xy_to_latlon(coverage["x_max"], coverage["y_max"])

    folium.Rectangle(
        bounds=[sw, ne],
        color="#2ecc71",
        fill=True,
        fill_color="#2ecc71",
        fill_opacity=0.05,
        weight=2,
        dash_array="6 4",
        tooltip="田块边界"
    ).add_to(layer)


def _add_track_line(layer, df):
    """将轨迹按段着色：正常蓝色，异常段橙色"""
    coords_normal = []
    prev_anomaly = "normal"

    # 收集正常连续段
    for _, row in df.iterrows():
        cur = row["anomaly"]
        if cur == "normal":
            coords_normal.append([row["latitude"], row["longitude"]])
        else:
            # 遇到异常点时，先把之前积累的正常段画出来
            if len(coords_normal) >= 2:
                folium.PolyLine(
                    coords_normal,
                    color="#2980b9",
                    weight=3,
                    opacity=0.85,
                    tooltip="正常作业段"
                ).add_to(layer)
            coords_normal = []
        prev_anomaly = cur

    # 画最后一段
    if len(coords_normal) >= 2:
        folium.PolyLine(
            coords_normal,
            color="#2980b9",
            weight=3,
            opacity=0.85,
            tooltip="正常作业段"
        ).add_to(layer)

    # 起点/终点标记（用 Emoji DivIcon，不依赖外部 CDN）
    start_html = (
        f'<div style="font-size:18px; text-align:center; line-height:1;">'
        f'<div style="background:#27ae60; color:white; border-radius:50%; width:24px; height:24px; '
        f'line-height:24px; font-weight:bold; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);">▶</div>'
        f'<div style="font-size:10px; color:#333; margin-top:2px; white-space:nowrap;">起点</div></div>'
    )
    folium.Marker(
        [df["latitude"].iloc[0], df["longitude"].iloc[0]],
        icon=folium.DivIcon(html=start_html, icon_size=(30, 36), icon_anchor=(15, 30)),
        popup=folium.Popup(
            f"<b>🟢 作业起点</b><br>"
            f"时间：{df['timestamp'].iloc[0].strftime('%H:%M:%S')}<br>"
            f"坐标：({df['latitude'].iloc[0]:.6f}, {df['longitude'].iloc[0]:.6f})",
            max_width=220
        ),
        tooltip=f"作业起点 {df['timestamp'].iloc[0].strftime('%H:%M:%S')}"
    ).add_to(layer)

    end_html = (
        f'<div style="font-size:18px; text-align:center; line-height:1;">'
        f'<div style="background:#e74c3c; color:white; border-radius:50%; width:24px; height:24px; '
        f'line-height:24px; font-weight:bold; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);">■</div>'
        f'<div style="font-size:10px; color:#333; margin-top:2px; white-space:nowrap;">终点</div></div>'
    )
    folium.Marker(
        [df["latitude"].iloc[-1], df["longitude"].iloc[-1]],
        icon=folium.DivIcon(html=end_html, icon_size=(30, 36), icon_anchor=(15, 30)),
        popup=folium.Popup(
            f"<b>🔴 作业终点</b><br>"
            f"时间：{df['timestamp'].iloc[-1].strftime('%H:%M:%S')}<br>"
            f"坐标：({df['latitude'].iloc[-1]:.6f}, {df['longitude'].iloc[-1]:.6f})",
            max_width=220
        ),
        tooltip=f"作业终点 {df['timestamp'].iloc[-1].strftime('%H:%M:%S')}"
    ).add_to(layer)


def _add_anomaly_markers(layer, df):
    """在异常点位置添加带 popup 的圆点标记"""
    anomaly_df = df[df["anomaly"] != "normal"]

    color_map = {
        "stop": ("#e74c3c", "停机异常"),
        "overspeed": ("#e74c3c", "超速/跳点"),
        "jerk": ("#f39c12", "加速度突变"),
    }

    for _, row in anomaly_df.iterrows():
        color, label = color_map.get(row["anomaly"], ("#95a5a6", "未知"))
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(
                f"<b>{label}</b><br>"
                f"时间：{row['timestamp'].strftime('%H:%M:%S')}<br>"
                f"速度：{row['speed_mps']:.2f} m/s<br>"
                f"坐标：({row['latitude']:.6f}, {row['longitude']:.6f})",
                max_width=200
            ),
            tooltip=f"{label}（{row['speed_mps']:.2f} m/s）"
        ).add_to(layer)


def _add_heatmap(layer, df, coverage):
    """基于栅格覆盖密度生成热力图"""
    # 用覆盖次数生成热力图数据点
    origin_lat = df["latitude"].iloc[0]
    origin_lon = df["longitude"].iloc[0]
    M_PER_LAT = 111320.0
    M_PER_LON = 111320.0 * math.cos(math.radians(origin_lat))

    grid = coverage["grid"]
    cell_size = coverage["cell_size"]
    ny, nx = grid.shape

    heat_data = []
    max_val = grid.max() if grid.max() > 0 else 1

    for gy in range(ny):
        for gx in range(nx):
            val = grid[gy, gx]
            if val > 0:
                x_m = coverage["x_min"] + gx * cell_size
                y_m = coverage["y_min"] + gy * cell_size
                lat = origin_lat + y_m / M_PER_LAT
                lon = origin_lon + x_m / M_PER_LON
                weight = val / max_val
                heat_data.append([lat, lon, weight])

    if heat_data:
        folium.plugins.HeatMap(
            heat_data,
            radius=12,
            blur=10,
            gradient={"0.3": "blue", "0.6": "lime", "1.0": "red"},
            min_opacity=0.3,
            name="覆盖热力图"
        ).add_to(layer)


def _add_info_panel(m, stats):
    """在地图左上角嵌入作业统计信息卡片（HTML 浮层）"""
    # 用红/橙/绿色表示质量等级
    def quality_color(rate, good_thresh, bad_thresh, higher_is_better=True):
        if higher_is_better:
            return "#27ae60" if rate >= good_thresh else ("#e67e22" if rate >= bad_thresh else "#e74c3c")
        else:
            return "#27ae60" if rate <= good_thresh else ("#e67e22" if rate <= bad_thresh else "#e74c3c")

    cov_color = quality_color(stats["coverage_rate"], 90, 75)
    miss_color = quality_color(stats["missed_rate"], 5, 15, False)
    ovlp_color = quality_color(stats["overlap_rate"], 10, 20, False)

    html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 1000;
         background: rgba(255,255,255,0.95); padding: 12px 16px;
         border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
         font-family: Arial, sans-serif; font-size: 13px; min-width: 220px;">
      <b style="font-size:15px;">📊 农机作业质量报告</b>
      <hr style="margin:6px 0; border-color:#ddd;">
      <table style="border-collapse:collapse; width:100%;">
        <tr><td>🕐 作业时长</td><td style="text-align:right;"><b>{stats['duration_min']} 分钟</b></td></tr>
        <tr><td>📏 作业里程</td><td style="text-align:right;"><b>{stats['total_distance_m']} 米</b></td></tr>
        <tr><td>⚡ 平均速度</td><td style="text-align:right;"><b>{stats['avg_speed_mps']} m/s</b></td></tr>
        <tr><td>⚠️ 异常点数</td><td style="text-align:right;"><b style="color:#e74c3c;">{stats['anomaly_count']}</b></td></tr>
        <tr><td colspan="2"><hr style="margin:4px 0; border-color:#ddd;"></td></tr>
        <tr><td>✅ 覆盖率</td><td style="text-align:right;">
          <b style="color:{cov_color};">{stats['coverage_rate']}%</b></td></tr>
        <tr><td>🚫 漏喷率</td><td style="text-align:right;">
          <b style="color:{miss_color};">{stats['missed_rate']}%</b></td></tr>
        <tr><td>🔁 重叠率</td><td style="text-align:right;">
          <b style="color:{ovlp_color};">{stats['overlap_rate']}%</b></td></tr>
      </table>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


def _add_legend(m):
    """添加图例"""
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 50px; z-index: 1000;
         background: rgba(255,255,255,0.95); padding: 10px 14px;
         border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
         font-family: Arial, sans-serif; font-size: 12px;">
      <b>图例</b><br>
      <span style="color:#2980b9;">━━</span> 正常作业轨迹<br>
      <span style="color:#e74c3c;">●</span> 停机 / 超速跳点<br>
      <span style="color:#f39c12;">●</span> 加速度突变<br>
      <span style="color:#27ae60;">▭</span> 田块边界<br>
      <span style="background:linear-gradient(to right,blue,lime,red);
             display:inline-block;width:40px;height:8px;vertical-align:middle;"></span> 覆盖热力
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
