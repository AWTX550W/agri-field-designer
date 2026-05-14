#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.py — RTK-GPS 农机作业数据核心处理模块
功能：数据加载清洗、经纬度→平面坐标转换、速度异常检测、栅格化覆盖率分析
"""

import json
import math
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any


# ============================================================
# 1. 数据加载与清洗
# ============================================================

def load_gps_trace(filepath: str) -> pd.DataFrame:
    """
    加载 GPS 轨迹 JSON 文件（每行一个 JSON 对象格式）
    自动过滤无效经纬度（超出合理范围）和重复时间戳
    """
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                records.append(obj)
            except json.JSONDecodeError:
                continue

    df = pd.DataFrame(records)

    # 必填字段检查
    required_cols = ["latitude", "longitude", "timestamp"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"GPS 数据缺少必填字段: {col}")

    # 过滤无效经纬度（中国范围：73°E~135°E, 18°N~53°N）
    before = len(df)
    df = df[
        (df["latitude"].between(18.0, 53.0)) &
        (df["longitude"].between(73.0, 135.0))
    ].copy()
    dropped = before - len(df)
    if dropped > 0:
        print(f"[清洗] 过滤 {dropped} 条无效经纬度记录")

    # 解析时间戳，过滤空值
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 去重（相同时间戳保留第一条）
    dup_count = df.duplicated(subset="timestamp").sum()
    if dup_count > 0:
        df = df.drop_duplicates(subset="timestamp", keep="first")
        print(f"[清洗] 去除 {dup_count} 条重复时间戳")

    print(f"[加载] 有效 GPS 记录：{len(df)} 条，时间范围：{df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
    return df


# ============================================================
# 2. 经纬度 → 平面坐标（局部切面投影）
# ============================================================

def latlon_to_xy(df: pd.DataFrame) -> pd.DataFrame:
    """
    以轨迹第一个点为原点，将经纬度转换为局部平面坐标 (x_m, y_m)，单位：米
    采用等距切面近似，精度满足农田级别（百米范围内误差 < 0.1m）
    """
    origin_lat = df["latitude"].iloc[0]
    origin_lon = df["longitude"].iloc[0]

    # 1° 纬度对应米数（约 111.32km）
    M_PER_LAT = 111320.0
    # 1° 经度对应米数（随纬度变化）
    M_PER_LON = 111320.0 * math.cos(math.radians(origin_lat))

    df = df.copy()
    df["x_m"] = (df["longitude"] - origin_lon) * M_PER_LON
    df["y_m"] = (df["latitude"] - origin_lat) * M_PER_LAT

    print(f"[坐标转换] 原点：({origin_lat:.6f}, {origin_lon:.6f})")
    print(f"[坐标转换] 作业范围 X: [{df['x_m'].min():.1f}, {df['x_m'].max():.1f}]m  "
          f"Y: [{df['y_m'].min():.1f}, {df['y_m'].max():.1f}]m")
    return df


# ============================================================
# 3. 速度计算与异常检测
# ============================================================

def compute_speed(df: pd.DataFrame) -> pd.DataFrame:
    """
    若原始数据无 speed_mps 字段，则由相邻点坐标差和时间差推算速度
    同时计算加速度（用于异常检测）
    """
    df = df.copy()

    if "speed_mps" not in df.columns:
        # 用坐标差推算速度
        dx = df["x_m"].diff()
        dy = df["y_m"].diff()
        dt = df["timestamp"].diff().dt.total_seconds()
        dist = np.sqrt(dx**2 + dy**2)
        df["speed_mps"] = (dist / dt).fillna(0)

    # 加速度（m/s²）
    dt = df["timestamp"].diff().dt.total_seconds().fillna(1)
    df["accel"] = df["speed_mps"].diff().abs() / dt
    df["accel"] = df["accel"].fillna(0)

    return df


def detect_anomalies(df: pd.DataFrame,
                     speed_low_thresh: float = 0.3,
                     speed_high_thresh: float = 8.0,
                     accel_thresh: float = 2.0) -> pd.DataFrame:
    """
    检测速度异常点，标记以下三类：
    - 'stop'   : 速度过低（近似停机，< speed_low_thresh m/s）
    - 'overspeed' : 速度过高（> speed_high_thresh m/s，可能 GPS 跳点）
    - 'jerk'   : 加速度突变（> accel_thresh m/s²，可能信号丢失后重连）
    """
    df = df.copy()
    df["anomaly"] = "normal"

    df.loc[df["speed_mps"] < speed_low_thresh, "anomaly"] = "stop"
    df.loc[df["speed_mps"] > speed_high_thresh, "anomaly"] = "overspeed"
    df.loc[(df["anomaly"] == "normal") & (df["accel"] > accel_thresh), "anomaly"] = "jerk"

    counts = df["anomaly"].value_counts()
    print(f"[异常检测] 正常点：{counts.get('normal', 0)} | "
          f"停机：{counts.get('stop', 0)} | "
          f"超速/跳点：{counts.get('overspeed', 0)} | "
          f"加速度突变：{counts.get('jerk', 0)}")
    return df


# ============================================================
# 4. 栅格化覆盖率分析（漏喷 / 重叠）
# ============================================================

def grid_coverage_analysis(df: pd.DataFrame,
                           working_width: float = 3.0,
                           cell_size: float = 1.0) -> Dict[str, Any]:
    """
    将作业轨迹投影到栅格地图，统计：
    - 覆盖率  : 至少被覆盖一次的栅格 / 田块总栅格
    - 漏喷率  : 未覆盖栅格 / 总栅格
    - 重叠率  : 被覆盖 ≥2 次的栅格 / 总栅格

    Args:
        working_width: 农机作业幅宽（米）
        cell_size:     栅格分辨率（米）
    """
    # 只分析正常点（排除停机和超速跳点）
    normal_df = df[df["anomaly"] != "overspeed"].copy()

    x_min, x_max = normal_df["x_m"].min(), normal_df["x_m"].max()
    y_min, y_max = normal_df["y_m"].min(), normal_df["y_m"].max()

    # 田块边界扩展半个幅宽作为缓冲
    buf = working_width / 2
    x_min -= buf; x_max += buf
    y_min -= buf; y_max += buf

    # 栅格尺寸
    nx = max(1, int((x_max - x_min) / cell_size))
    ny = max(1, int((y_max - y_min) / cell_size))
    grid = np.zeros((ny, nx), dtype=np.int16)  # 记录覆盖次数

    half_w = working_width / 2 / cell_size  # 幅宽在栅格中的半径

    for _, row in normal_df.iterrows():
        # 将点坐标转换为栅格索引
        gx = int((row["x_m"] - x_min) / cell_size)
        gy = int((row["y_m"] - y_min) / cell_size)

        # 以幅宽为半径，将周围栅格标记为已覆盖
        r = max(1, int(half_w))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx_ = gx + dx
                ny_ = gy + dy
                if 0 <= nx_ < nx and 0 <= ny_ < ny:
                    if dx**2 + dy**2 <= (half_w)**2:
                        grid[ny_, nx_] += 1

    total_cells = ny * nx
    covered_cells = np.sum(grid >= 1)
    overlap_cells = np.sum(grid >= 2)
    uncovered_cells = total_cells - covered_cells

    result = {
        "grid": grid,
        "x_min": x_min, "x_max": x_max,
        "y_min": y_min, "y_max": y_max,
        "cell_size": cell_size,
        "working_width": working_width,
        "total_cells": int(total_cells),
        "covered_cells": int(covered_cells),
        "overlap_cells": int(overlap_cells),
        "uncovered_cells": int(uncovered_cells),
        "coverage_rate": round(covered_cells / total_cells * 100, 2),
        "missed_rate": round(uncovered_cells / total_cells * 100, 2),
        "overlap_rate": round(overlap_cells / total_cells * 100, 2),
    }

    print(f"\n[栅格分析] 田块 {nx}×{ny} 栅格（{cell_size}m 分辨率）")
    print(f"  覆盖率：{result['coverage_rate']}%  |  "
          f"漏喷率：{result['missed_rate']}%  |  "
          f"重叠率：{result['overlap_rate']}%")
    return result


# ============================================================
# 5. 整体统计指标
# ============================================================

def compute_statistics(df: pd.DataFrame, coverage: Dict[str, Any]) -> Dict[str, Any]:
    """汇总作业统计信息，用于报告生成"""
    duration_s = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).total_seconds()
    total_dist = 0.0
    for i in range(1, len(df)):
        dx = df["x_m"].iloc[i] - df["x_m"].iloc[i-1]
        dy = df["y_m"].iloc[i] - df["y_m"].iloc[i-1]
        total_dist += math.sqrt(dx**2 + dy**2)

    normal_speeds = df.loc[df["anomaly"] == "normal", "speed_mps"]

    return {
        "start_time": df["timestamp"].iloc[0].strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": df["timestamp"].iloc[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "duration_min": round(duration_s / 60, 1),
        "total_points": len(df),
        "total_distance_m": round(total_dist, 1),
        "avg_speed_mps": round(normal_speeds.mean(), 2) if len(normal_speeds) > 0 else 0,
        "max_speed_mps": round(df["speed_mps"].max(), 2),
        "min_speed_mps": round(df["speed_mps"].min(), 2),
        "anomaly_count": int((df["anomaly"] != "normal").sum()),
        "stop_count": int((df["anomaly"] == "stop").sum()),
        "overspeed_count": int((df["anomaly"] == "overspeed").sum()),
        "jerk_count": int((df["anomaly"] == "jerk").sum()),
        "coverage_rate": coverage["coverage_rate"],
        "missed_rate": coverage["missed_rate"],
        "overlap_rate": coverage["overlap_rate"],
        "working_width_m": coverage["working_width"],
        "field_area_m2": round(
            (coverage["x_max"] - coverage["x_min"]) *
            (coverage["y_max"] - coverage["y_min"]), 1
        ),
    }
