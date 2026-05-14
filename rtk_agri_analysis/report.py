#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report.py — 农机作业质量 Markdown 报告自动生成模块
输出：output/agri_work_report.md
"""

import os
from datetime import datetime
from typing import Dict, Any
import pandas as pd


def generate_report(df: pd.DataFrame,
                    stats: Dict[str, Any],
                    coverage: Dict[str, Any],
                    output_path: str = "output/agri_work_report.md"):
    """
    自动生成完整的 Markdown 格式作业质量分析报告
    包含：封面信息、执行摘要、作业统计、质量指标、异常详情、优化建议
    """

    # ── 质量等级评定 ──
    def grade_coverage(rate):
        if rate >= 95: return "★★★★★ 优秀"
        if rate >= 90: return "★★★★☆ 良好"
        if rate >= 80: return "★★★☆☆ 合格"
        return "★★☆☆☆ 需改进"

    def grade_miss(rate):
        if rate <= 2:  return "★★★★★ 优秀"
        if rate <= 5:  return "★★★★☆ 良好"
        if rate <= 10: return "★★★☆☆ 合格"
        return "★★☆☆☆ 需改进"

    def grade_overlap(rate):
        if rate <= 5:  return "★★★★★ 优秀"
        if rate <= 10: return "★★★★☆ 良好"
        if rate <= 20: return "★★★☆☆ 合格"
        return "★★☆☆☆ 需改进"

    # ── 异常点详情表格 ──
    anomaly_df = df[df["anomaly"] != "normal"].copy()
    anomaly_rows = ""
    for _, row in anomaly_df.iterrows():
        type_cn = {"stop": "停机", "overspeed": "超速/跳点", "jerk": "加速度突变"}.get(row["anomaly"], "未知")
        anomaly_rows += (
            f"| {row['timestamp'].strftime('%H:%M:%S')} "
            f"| {type_cn} "
            f"| {row['speed_mps']:.2f} m/s "
            f"| {row['latitude']:.6f}, {row['longitude']:.6f} |\n"
        )
    if not anomaly_rows:
        anomaly_rows = "| — | 无异常 | — | — |\n"

    # ── 优化建议 ──
    suggestions = []
    if stats["missed_rate"] > 10:
        suggestions.append(f"- ⚠️ 漏喷率 **{stats['missed_rate']}%** 偏高，建议缩小行间距或增大作业幅宽至 {stats['working_width_m'] + 0.5:.1f}m")
    if stats["overlap_rate"] > 20:
        suggestions.append(f"- ⚠️ 重叠率 **{stats['overlap_rate']}%** 偏高，建议增大行间距或启用 GPS 辅助自动驾驶对行")
    if stats["stop_count"] > 0:
        suggestions.append(f"- ⚠️ 检测到 **{stats['stop_count']}** 次停机，建议排查机械故障或操作习惯")
    if stats["overspeed_count"] > 0:
        suggestions.append(f"- ⚠️ 检测到 **{stats['overspeed_count']}** 个 GPS 跳点，建议检查 RTK 信号质量（HDOP 应 < 1.5）")
    if stats["jerk_count"] > 0:
        suggestions.append(f"- ℹ️ **{stats['jerk_count']}** 处加速度突变，可能为转弯/信号恢复，建议核查")
    if not suggestions:
        suggestions.append("- ✅ 本次作业质量优秀，各项指标均在推荐范围内")

    suggestions_text = "\n".join(suggestions)

    # ── 报告内容 ──
    report = f"""# 🚜 农机 RTK-GPS 作业质量分析报告

> 报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 分析工具：RTK-GPS 农机作业质量分析系统 v1.0

---

## 一、作业基本信息

| 项目 | 数值 |
|------|------|
| 作业开始时间 | {stats['start_time']} |
| 作业结束时间 | {stats['end_time']} |
| 作业总时长 | {stats['duration_min']} 分钟 |
| GPS 轨迹点数 | {stats['total_points']} 条 |
| 作业里程 | {stats['total_distance_m']} 米 |
| 田块面积（估算）| {stats['field_area_m2']} m² （{stats['field_area_m2']/10000:.3f} 亩） |
| 作业幅宽 | {stats['working_width_m']} 米 |

---

## 二、速度统计

| 指标 | 数值 |
|------|------|
| 平均作业速度 | {stats['avg_speed_mps']} m/s（{stats['avg_speed_mps']*3.6:.1f} km/h）|
| 最高速度 | {stats['max_speed_mps']} m/s |
| 最低速度（非停机）| {stats['min_speed_mps']} m/s |

---

## 三、作业质量指标

| 质量指标 | 数值 | 评级 |
|----------|------|------|
| ✅ 覆盖率 | **{stats['coverage_rate']}%** | {grade_coverage(stats['coverage_rate'])} |
| 🚫 漏喷率 | **{stats['missed_rate']}%** | {grade_miss(stats['missed_rate'])} |
| 🔁 重叠率 | **{stats['overlap_rate']}%** | {grade_overlap(stats['overlap_rate'])} |

> 覆盖率目标 ≥ 90%，漏喷率目标 ≤ 5%，重叠率目标 ≤ 15%（参考农业机械化标准）

---

## 四、异常点检测

共检测到异常点 **{stats['anomaly_count']}** 处：
- 停机异常：{stats['stop_count']} 处
- 超速/GPS 跳点：{stats['overspeed_count']} 处
- 加速度突变：{stats['jerk_count']} 处

### 异常点详情

| 时间 | 类型 | 速度 | 坐标（纬度, 经度）|
|------|------|------|-----------------|
{anomaly_rows}
---

## 五、栅格分析参数

| 参数 | 值 |
|------|-----|
| 栅格分辨率 | {coverage['cell_size']} m |
| 作业幅宽 | {coverage['working_width']} m |
| 总栅格数 | {coverage['total_cells']} |
| 已覆盖栅格 | {coverage['covered_cells']} |
| 重叠栅格 | {coverage['overlap_cells']} |
| 未覆盖栅格 | {coverage['uncovered_cells']} |

---

## 六、优化建议

{suggestions_text}

---

## 七、可视化地图

交互式地图已生成：`output/agri_work_map.html`

地图包含：
- 蓝色轨迹线：正常作业路径
- 红色圆点：停机 / GPS 跳点异常
- 黄色圆点：加速度突变
- 绿色虚线框：田块边界
- 热力图层：作业覆盖密度分布

---

*本报告由 RTK-GPS 农机作业质量分析系统自动生成，仅供参考。*
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[报告] 已保存至 {output_path}")
    return report
