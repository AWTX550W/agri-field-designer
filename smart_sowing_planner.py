# -*- coding: utf-8 -*-
"""
智能播种规划器 - AI优化播种密度与布局
基于作物生长模型和空间优化算法
"""

import numpy as np
import sys
from typing import List, Tuple

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class SowingPlanner:
    """播种规划AI"""

    def __init__(self, crop_type: str = "tomato"):
        self.crop_type = crop_type

        # 作物参数数据库（可扩展）
        self.crop_params = {
            "tomato": {
                "row_spacing": 0.6,      # 行距(m)
                "plant_spacing": 0.4,    # 株距(m)
                "root_depth": 0.5,       # 根系深度(m)
                "canopy_radius": 0.3,    # 冠幅半径(m)
                "water_per_plant": 5,    # 单株需水量(L/天)
                "fertilizer_n": 10,      # 氮肥需求(g/季)
            },
            "corn": {
                "row_spacing": 0.8,
                "plant_spacing": 0.5,
                "root_depth": 0.8,
                "canopy_radius": 0.5,
                "water_per_plant": 15,
                "fertilizer_n": 30,
            },
            "wheat": {
                "row_spacing": 0.25,
                "plant_spacing": 0.15,
                "root_depth": 0.4,
                "canopy_radius": 0.15,
                "water_per_plant": 2,
                "fertilizer_n": 8,
            }
        }

    def optimize_density(self, field_area: float, soil_fertility: str = "medium"):
        """
        优化播种密度
        :param field_area: 地块面积(亩)
        :param soil_fertility: 土壤肥力等级 (low/medium/high)
        :return: 推荐株数、行数、株距调整
        """
        params = self.crop_params[self.crop_type]
        base_density = 1 / (params["row_spacing"] * params["plant_spacing"])  # 株/平方米

        # 肥力系数
        fertility_factor = {"low": 0.9, "medium": 1.0, "high": 1.1}[soil_fertility]

        # 最终密度
        optimal_density = base_density * fertility_factor  # 株/平方米
        total_plants = int(optimal_density * field_area * 666.67)  # 亩→平方米转换

        # 生成种植布局坐标
        rows = int(np.sqrt(field_area * 666.67 / (params["plant_spacing"] / params["row_spacing"])))
        plants_per_row = total_plants // rows

        layout = []
        for i in range(rows):
            row_x = i * params["row_spacing"]
            for j in range(plants_per_row):
                plant_y = j * params["plant_spacing"]
                layout.append((row_x, plant_y))

        return {
            "作物": self.crop_type,
            "地块面积(亩)": field_area,
            "土壤肥力": soil_fertility,
            "推荐总株数": total_plants,
            "种植行数": rows,
            "每行株数": plants_per_row,
            "行距(m)": params["row_spacing"],
            "株距(m)": params["plant_spacing"],
            "布局坐标": layout[:5]  # 仅展示前5个点
        }

    def generate_sowing_path(self, field_length: float, field_width: float) -> List[Tuple[float, float]]:
        """
        生成智能播种路径（类似无人机路径规划）
        :return: 路径点列表 [(x1,y1), (x2,y2), ...]
        """
        params = self.crop_params[self.crop_type]
        step = params["row_spacing"]

        path = []
        direction = 1  # 1: 正向, -1: 反向

        for y in np.arange(0, field_width, step):
            if direction == 1:
                # 从左到右
                x_points = np.arange(0, field_length, 0.2)
            else:
                # 从右到左
                x_points = np.arange(field_length, 0, -0.2)

            for x in x_points:
                path.append((round(x, 2), round(y, 2)))

            direction *= -1

        return path


# ============ 示例用法 ============

if __name__ == "__main__":
    print("🌱 智能播种规划器已就绪\n")

    # 示例1: 优化番茄播种密度（10亩地，中等肥力）
    planner = SowingPlanner("tomato")
    plan = planner.optimize_density(field_area=10, soil_fertility="medium")
    print("📋 播种方案:")
    for k, v in plan.items():
        if k != "布局坐标":
            print(f"   {k}: {v}")

    # 示例2: 生成播种路径（100m×80m地块）
    print("\n🚜 播种路径规划:")
    path = planner.generate_sowing_path(field_length=100, field_width=80)
    print(f"   总路径点数: {len(path)}")
    print(f"   前5个点: {path[:5]}")
    print(f"   最后5个点: {path[-5:]}")

    print("\n💡 使用提示:")
    print("   1. 修改 crop_type 为 'corn' 或 'wheat' 适配不同作物")
    print("   2. 调整 soil_fertility 参数适配地块肥力")
    print("   3. 路径可直接导入农机自动驾驶系统")
    print("   4. 结合GPS坐标可实现精准播种")
