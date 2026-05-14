#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — RTK-GPS 农机作业质量分析工具 · 程序入口
一键运行全流程：加载数据 → 分析 → 可视化 → 生成报告

使用方法：
    python main.py
    # 或指定数据文件路径
    python main.py --data data/gps_trace.json
    # 或指定作业幅宽
    python main.py --data data/gps_trace.json --width 4.0
"""

import argparse
import os
import sys
from pathlib import Path

# 添加当前目录到 Python 路径（确保可以 import 同目录模块）
sys.path.insert(0, str(Path(__file__).parent))

from core import load_gps_trace, latlon_to_xy, compute_speed, detect_anomalies, grid_coverage_analysis, compute_statistics
from visualize import build_map
from report import generate_report


def run(data_path: str = "data/gps_trace.json",
        working_width: float = 3.0,
        cell_size: float = 1.0,
        output_dir: str = "output"):
    """
    完整分析流程
    """
    print("=" * 60)
    print("🚜 RTK-GPS 农机作业质量分析系统 v1.0")
    print("=" * 60)

    # ── 步骤1：加载并清洗 GPS 数据 ──
    print("\n>>> 步骤 1/5：加载 GPS 轨迹数据 ...")
    df = load_gps_trace(data_path)

    # ── 步骤2：坐标转换 ──
    print("\n>>> 步骤 2/5：经纬度 → 平面坐标 ...")
    df = latlon_to_xy(df)

    # ── 步骤3：速度计算与异常检测 ──
    print("\n>>> 步骤 3/5：速度异常检测 ...")
    df = compute_speed(df)
    df = detect_anomalies(df)

    # ── 步骤4：栅格覆盖率分析 ──
    print("\n>>> 步骤 4/5：栅格化覆盖率分析 ...")
    coverage = grid_coverage_analysis(df, working_width=working_width, cell_size=cell_size)

    # ── 步骤5：统计指标汇总 ──
    print("\n>>> 步骤 5/5：生成报告 ...")
    stats = compute_statistics(df, coverage)

    # 打印核心指标
    print("\n" + "=" * 40)
    print("📊 核心指标速览")
    print("=" * 40)
    print(f"  作业时长  : {stats['duration_min']} 分钟")
    print(f"  作业里程  : {stats['total_distance_m']} 米")
    print(f"  平均速度  : {stats['avg_speed_mps']} m/s")
    print(f"  异常点数  : {stats['anomaly_count']}")
    print(f"  ✅ 覆盖率  : {stats['coverage_rate']}%")
    print(f"  🚫 漏喷率  : {stats['missed_rate']}%")
    print(f"  🔁 重叠率  : {stats['overlap_rate']}%")
    print("=" * 40)

    # ── 生成可视化地图 ──
    map_path = os.path.join(output_dir, "agri_work_map.html")
    build_map(df, coverage, stats, output_path=map_path)

    # ── 生成 Markdown 报告 ──
    report_path = os.path.join(output_dir, "agri_work_report.md")
    generate_report(df, stats, coverage, output_path=report_path)

    print("\n✅ 全流程完成！")
    print(f"   地图文件：{map_path}")
    print(f"   报告文件：{report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RTK-GPS 农机作业质量分析工具")
    parser.add_argument("--data", default="data/gps_trace.json",
                        help="GPS 轨迹 JSON 文件路径（每行一个 JSON 对象）")
    parser.add_argument("--width", type=float, default=3.0,
                        help="农机作业幅宽（米），默认 3.0m")
    parser.add_argument("--cell", type=float, default=1.0,
                        help="栅格分辨率（米），默认 1.0m")
    parser.add_argument("--output", default="output",
                        help="输出目录，默认 output/")

    args = parser.parse_args()

    # 支持相对路径（相对于本文件所在目录）
    if not os.path.isabs(args.data):
        args.data = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.data)
    if not os.path.isabs(args.output):
        args.output = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)

    run(
        data_path=args.data,
        working_width=args.width,
        cell_size=args.cell,
        output_dir=args.output,
    )
