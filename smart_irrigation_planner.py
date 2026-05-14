# -*- coding: utf-8 -*-
"""
智能灌溉规划器 - AI驱动精准灌溉
根据土壤湿度、天气预报、作物需水量自动计算灌溉方案
"""

import numpy as np
import sys
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


class SoilType(Enum):
    """土壤类型"""
    SANDY = "sandy"           # 砂土 - 排水快、保水差
    LOAMY = "loamy"           # 壤土 - 中等
    CLAY = "clay"             # 粘土 - 保水好、排水差
    SILTY = "silty"           # 粉砂土


class WeatherCondition(Enum):
    """天气状况"""
    SUNNY = "sunny"           # 晴天
    CLOUDY = "cloudy"         # 多云
    RAINY = "rainny"          # 下雨
    STORMY = "stormy"         # 暴风雨


@dataclass
class SoilData:
    """土壤数据"""
    moisture: float           # 当前湿度 0-1 (0=干, 1=湿)
    temperature: float         # 土壤温度 (°C)
    soil_type: SoilType       # 土壤类型
    depth: float              # 测量深度 (m)
    location: str             # 位置标识


@dataclass
class WeatherForecast:
    """天气预报"""
    date: datetime
    condition: WeatherCondition
    temperature_high: float    # 最高温 (°C)
    temperature_low: float    # 最低温 (°C)
    humidity: float           # 空气湿度 0-1
    precipitation: float     # 降水量 (mm)
    wind_speed: float         # 风速 (m/s)
    uv_index: float           # 紫外线指数


@dataclass
class CropWaterNeed:
    """作物需水量"""
    name: str
    daily_need: float          # 日需水量 (L/株)
    root_depth: float         # 根系深度 (m)
    drought_tolerance: float  # 耐旱程度 0-1 (越高越耐旱)
    growth_stage: str         # 生长阶段


@dataclass
class IrrigationPlan:
    """灌溉方案"""
    total_water: float        # 总用水量 (L)
    duration: float           # 灌溉时长 (分钟)
    flow_rate: float          # 流量 (L/小时)
    start_time: datetime      # 开始时间
    recommended_days: List[int]  # 建议灌溉日 (周几, 0=周一)
    confidence: float         # 方案置信度 0-1
    warnings: List[str]       # 警告信息


class SmartIrrigationPlanner:
    """
    智能灌溉规划器

    功能：
    1. 土壤湿度分析
    2. 天气预报整合
    3. 作物需水量计算
    4. 灌溉方案生成
    5. 节水优化建议
    """

    def __init__(self):
        # 作物需水量数据库 (L/株/天)
        self.crop_water_db = {
            "tomato": {
                "daily_need": 5.0,
                "root_depth": 0.5,
                "drought_tolerance": 0.3,
                "stages": {
                    "seedling": 0.5,    # 幼苗期需水量的50%
                    "vegetative": 0.8,
                    "flowering": 1.2,   # 开花期需水最多
                    "fruiting": 1.0,
                    "ripening": 0.7
                }
            },
            "corn": {
                "daily_need": 15.0,
                "root_depth": 0.8,
                "drought_tolerance": 0.4,
                "stages": {
                    "seedling": 0.4,
                    "vegetative": 0.8,
                    "tasseling": 1.3,  # 抽穗期
                    "grain_filling": 1.1,
                    "maturity": 0.5
                }
            },
            "wheat": {
                "daily_need": 2.5,
                "root_depth": 0.4,
                "drought_tolerance": 0.5,
                "stages": {
                    "seedling": 0.5,
                    "tillering": 0.7,
                    "heading": 1.2,
                    "grain_filling": 1.0,
                    "maturity": 0.3
                }
            },
            "strawberry": {
                "daily_need": 3.0,
                "root_depth": 0.3,
                "drought_tolerance": 0.2,  # 不耐旱
                "stages": {
                    "vegetative": 0.6,
                    "flowering": 1.0,
                    "fruiting": 1.2,
                    "dormancy": 0.2
                }
            },
            "cucumber": {
                "daily_need": 7.0,
                "root_depth": 0.4,
                "drought_tolerance": 0.25,
                "stages": {
                    "seedling": 0.4,
                    "vine_growth": 0.8,
                    "flowering": 1.1,
                    "fruiting": 1.3,  # 结果期需水最多
                    "harvest": 0.9
                }
            }
        }

        # 土壤类型参数
        self.soil_params = {
            SoilType.SANDY: {
                "field_capacity": 0.3,   # 田间持水量
                "wilting_point": 0.1,    # 凋萎系数
                "water_holding": 0.5,    # 保水能力系数
                "infiltration_rate": 30   # 渗透速率 (mm/h)
            },
            SoilType.LOAMY: {
                "field_capacity": 0.45,
                "wilting_point": 0.15,
                "water_holding": 0.8,
                "infiltration_rate": 15
            },
            SoilType.CLAY: {
                "field_capacity": 0.55,
                "wilting_point": 0.2,
                "water_holding": 1.0,
                "infiltration_rate": 5
            },
            SoilType.SILTY: {
                "field_capacity": 0.5,
                "wilting_point": 0.12,
                "water_holding": 0.9,
                "infiltration_rate": 10
            }
        }

    def analyze_soil_moisture(self, soil: SoilData) -> Dict:
        """
        分析土壤湿度状态

        :param soil: 土壤数据
        :return: 分析结果字典
        """
        params = self.soil_params[soil.soil_type]

        # 计算有效水分
        available_water = soil.moisture - params["wilting_point"]
        max_available = params["field_capacity"] - params["wilting_point"]
        water_percent = max(0, min(100, available_water / max_available * 100))

        # 判断状态
        if water_percent < 30:
            status = "干旱"
            status_level = "critical"
        elif water_percent < 50:
            status = "偏低"
            status_level = "warning"
        elif water_percent < 70:
            status = "适宜"
            status_level = "good"
        elif water_percent < 85:
            status = "充足"
            status_level = "good"
        else:
            status = "过湿"
            status_level = "flooding"

        return {
            "status": status,
            "status_level": status_level,
            "water_percent": round(water_percent, 1),
            "available_water_mm": round(available_water * 1000 * soil.depth, 1),
            "field_capacity": params["field_capacity"],
            "wilting_point": params["wilting_point"],
            "recommendation": self._get_moisture_recommendation(status_level, soil.soil_type)
        }

    def _get_moisture_recommendation(self, status: str, soil_type: SoilType) -> str:
        """根据湿度状态给出建议"""
        recommendations = {
            "critical": "紧急灌溉！土壤严重缺水，建议立即进行灌溉。",
            "warning": "需要灌溉，建议在未来24小时内进行灌溉。",
            "good": "土壤湿度适宜，可延迟1-2天再灌溉。",
            "flooding": "土壤过湿，可能导致根系腐烂，建议加强排水。"
        }
        base = recommendations.get(status, "")

        if soil_type == SoilType.SANDY:
            base += " 砂土保水性差，应采用少量多次灌溉方式。"
        elif soil_type == SoilType.CLAY:
            base += " 粘土渗透慢，应控制灌溉量，避免积水。"

        return base

    def calculate_crop_water_need(
        self,
        crop_type: str,
        plant_count: int,
        growth_stage: str = "vegetative",
        area: Optional[float] = None
    ) -> CropWaterNeed:
        """
        计算作物需水量

        :param crop_type: 作物类型
        :param plant_count: 植株数量
        :param growth_stage: 生长阶段
        :param area: 田地面积 (平方米)，可选
        :return: 作物需水量
        """
        if crop_type not in self.crop_water_db:
            raise ValueError(f"不支持的作物类型: {crop_type}，支持: {list(self.crop_water_db.keys())}")

        crop_data = self.crop_water_db[crop_type]
        stage_multiplier = crop_data["stages"].get(growth_stage, 1.0)

        daily_need = crop_data["daily_need"] * plant_count * stage_multiplier

        return CropWaterNeed(
            name=crop_type,
            daily_need=round(daily_need, 2),
            root_depth=crop_data["root_depth"],
            drought_tolerance=crop_data["drought_tolerance"],
            growth_stage=growth_stage
        )

    def adjust_for_weather(
        self,
        water_need: CropWaterNeed,
        forecast: WeatherForecast,
        soil: SoilData
    ) -> float:
        """
        根据天气预报调整灌溉量

        :param water_need: 基础需水量
        :param forecast: 天气预报
        :param soil: 当前土壤数据
        :return: 调整后的灌溉量 (L)
        """
        adjusted_need = water_need.daily_need

        # 温度调整
        if forecast.temperature_high > 35:
            adjusted_need *= 1.3  # 高温增加蒸发
        elif forecast.temperature_high < 20:
            adjusted_need *= 0.7  # 低温减少蒸发

        # 降水调整
        effective_rain = forecast.precipitation * 0.8  # 假设80%有效降水
        adjusted_need -= effective_rain * (soil.depth * 1000)  # 折算到每株
        adjusted_need = max(0, adjusted_need)

        # 湿度调整
        if forecast.humidity < 0.4:
            adjusted_need *= 1.2  # 干燥天气增加蒸发

        # 风速调整
        if forecast.wind_speed > 5:
            adjusted_need *= 1.15

        # 土壤保水能力调整
        params = self.soil_params[soil.soil_type]
        adjusted_need *= params["water_holding"]

        return round(max(0, adjusted_need), 2)

    def generate_irrigation_plan(
        self,
        soil: SoilData,
        crops: List[CropWaterNeed],
        forecasts: List[WeatherForecast],
        field_area: float,
        flow_rate: float = 500  # 默认滴灌流量 L/小时
    ) -> IrrigationPlan:
        """
        生成智能灌溉方案

        :param soil: 土壤数据
        :param crops: 作物需水量列表
        :param forecasts: 天气预报列表 (未来几天)
        :param field_area: 田地面积 (平方米)
        :param flow_rate: 灌溉系统流量 (L/小时)
        :return: 灌溉方案
        """
        # 1. 分析土壤湿度
        soil_analysis = self.analyze_soil_moisture(soil)
        print(f"📊 土壤分析: {soil_analysis['status']} ({soil_analysis['water_percent']}%)")

        # 2. 计算总需水量
        total_need = sum(crop.daily_need for crop in crops)
        print(f"🌱 作物需水量: {total_need:.1f}L/天")

        # 3. 考虑天气预报调整
        if forecasts:
            next_forecast = forecasts[0]
            adjusted_need = self.adjust_for_weather(
                CropWaterNeed("temp", total_need, 0.5, 0.5, "vegetative"),
                next_forecast,
                soil
            )
            print(f"⛅ 天气预报调整后: {adjusted_need:.1f}L")

            # 如果有雨，减少灌溉
            if next_forecast.condition == WeatherCondition.RAINY:
                adjusted_need *= 0.3
                print("🌧️ 今日有雨，大幅减少灌溉量")
            elif next_forecast.condition == WeatherCondition.STORMY:
                adjusted_need *= 0.1
                print("⛈️ 暴风雨天气，暂停灌溉")

        # 4. 根据土壤湿度调整
        if soil_analysis["status_level"] == "critical":
            adjusted_need = max(adjusted_need, total_need * 1.2)
        elif soil_analysis["status_level"] == "flooding":
            adjusted_need = 0
            print("⚠️ 土壤过湿，跳过本次灌溉")

        # 5. 计算灌溉时长
        duration_hours = adjusted_need / flow_rate
        duration_minutes = duration_hours * 60

        # 6. 生成警告信息
        warnings = []
        if soil_analysis["status_level"] == "critical":
            warnings.append("⚠️ 土壤严重缺水，请立即灌溉！")
        if any(f.condition == WeatherCondition.STORMY for f in forecasts[:2]):
            warnings.append("⚠️ 未来几天有暴风雨，请关注排水系统")
        if soil.soil_type == SoilType.SANDY:
            warnings.append("💡 提示: 砂土建议采用滴灌，少量多次")

        # 7. 计算置信度
        confidence = 0.7
        if len(forecasts) >= 3:
            confidence += 0.15
        if soil.moisture > 0.2:
            confidence += 0.1
        confidence = min(0.95, confidence)

        # 8. 建议灌溉日 (避开雨天)
        recommended_days = []
        for i, fc in enumerate(forecasts[:7]):
            if fc.condition not in [WeatherCondition.RAINY, WeatherCondition.STORMY]:
                recommended_days.append(fc.date.weekday())

        return IrrigationPlan(
            total_water=round(adjusted_need, 1),
            duration=round(duration_minutes, 1),
            flow_rate=flow_rate,
            start_time=datetime.now().replace(hour=6, minute=0, second=0, microsecond=0),
            recommended_days=recommended_days[:3],
            confidence=confidence,
            warnings=warnings
        )

    def get_irrigation_schedule(
        self,
        soil: SoilData,
        crops: List[CropWaterNeed],
        days: int = 7
    ) -> List[Dict]:
        """
        生成一周灌溉计划

        :param soil: 土壤数据
        :param crops: 作物需水量列表
        :param days: 计划天数
        :return: 每日灌溉计划列表
        """
        schedule = []
        current_moisture = soil.moisture

        for day in range(days):
            plan_date = datetime.now() + timedelta(days=day)

            # 模拟土壤水分变化
            daily_loss = sum(crop.daily_need for crop in crops) / 1000  # 转换为m³

            # 每日自然蒸发
            evaporation = 0.002 * (plan_date.timetuple().tm_yday / 30)  # 随季节变化

            current_moisture -= (daily_loss + evaporation) / soil.depth

            # 限制范围
            current_moisture = max(0.05, min(0.9, current_moisture))

            # 判断是否需要灌溉
            needs_irrigation = current_moisture < 0.35

            schedule.append({
                "date": plan_date.strftime("%Y-%m-%d"),
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][plan_date.weekday()],
                "soil_moisture": round(current_moisture * 100, 1),
                "needs_irrigation": needs_irrigation,
                "water_amount": round(sum(c.daily_need for c in crops) * 1.2, 1) if needs_irrigation else 0
            })

        return schedule

    def optimize_water_usage(
        self,
        total_water_budget: float,
        crops: List[CropWaterNeed],
        soil: SoilData
    ) -> Dict:
        """
        优化水资源分配

        当水资源有限时，如何分配给不同作物

        :param total_water_budget: 总水资源限制 (L)
        :param crops: 作物列表
        :param soil: 土壤数据
        :return: 优化方案
        """
        if not crops:
            return {"allocation": [], "shortage": 0, "message": "无作物数据"}

        total_need = sum(c.daily_need for c in crops)

        if total_need <= total_water_budget:
            return {
                "allocation": [{"crop": c.name, "water": c.daily_need, "full": True} for c in crops],
                "shortage": 0,
                "message": "水资源充足，可满足所有作物需求"
            }

        # 按优先级分配 (耐旱性低的优先)
        sorted_crops = sorted(crops, key=lambda x: x.drought_tolerance)

        shortage = total_need - total_water_budget
        allocation = []
        remaining = total_water_budget

        for crop in sorted_crops:
            if remaining >= crop.daily_need:
                allocation.append({"crop": crop.name, "water": crop.daily_need, "full": True})
                remaining -= crop.daily_need
            else:
                ratio = remaining / crop.daily_need
                allocation.append({"crop": crop.name, "water": remaining, "full": False, "ratio": round(ratio, 2)})
                remaining = 0

        return {
            "allocation": allocation,
            "shortage": round(shortage, 1),
            "message": f"水资源不足，缺少 {shortage:.1f}L，将优先保障不耐旱作物"
        }


# ============ 测试代码 ============
if __name__ == "__main__":
    print("=" * 50)
    print("🌊 智能灌溉规划系统 - 测试")
    print("=" * 50)

    # 创建规划器
    planner = SmartIrrigationPlanner()

    # 1. 土壤数据分析
    print("\n📍 测试1: 土壤湿度分析")
    soil = SoilData(
        moisture=0.25,
        temperature=25.0,
        soil_type=SoilType.LOAMY,
        depth=0.3,
        location="1号田"
    )

    analysis = planner.analyze_soil_moisture(soil)
    print(f"   状态: {analysis['status']}")
    print(f"   有效水分: {analysis['water_percent']}%")
    print(f"   建议: {analysis['recommendation']}")

    # 2. 作物需水量计算
    print("\n📍 测试2: 作物需水量计算")
    corn = planner.calculate_crop_water_need("corn", 100, "tasseling")
    print(f"   玉米(抽穗期) 100株: {corn.daily_need}L/天")

    tomato = planner.calculate_crop_water_need("tomato", 200, "fruiting")
    print(f"   番茄(结果期) 200株: {tomato.daily_need}L/天")

    # 3. 生成灌溉方案
    print("\n📍 测试3: 生成灌溉方案")
    forecasts = [
        WeatherForecast(
            date=datetime.now(),
            condition=WeatherCondition.SUNNY,
            temperature_high=32,
            temperature_low=24,
            humidity=0.5,
            precipitation=0,
            wind_speed=2,
            uv_index=8
        ),
        WeatherForecast(
            date=datetime.now() + timedelta(days=1),
            condition=WeatherCondition.CLOUDY,
            temperature_high=28,
            temperature_low=22,
            humidity=0.65,
            precipitation=2,
            wind_speed=3,
            uv_index=4
        )
    ]

    crops = [corn, tomato]
    plan = planner.generate_irrigation_plan(soil, crops, forecasts, field_area=500)

    print(f"   建议灌溉量: {plan.total_water}L")
    print(f"   灌溉时长: {plan.duration}分钟")
    print(f"   置信度: {plan.confidence:.0%}")
    if plan.warnings:
        print(f"   警告: {', '.join(plan.warnings)}")

    # 4. 一周灌溉计划
    print("\n📍 测试4: 一周灌溉计划")
    schedule = planner.get_irrigation_schedule(soil, crops, days=7)
    for day in schedule:
        status = "✅ 灌溉" if day["needs_irrigation"] else "⏭️ 跳过"
        water = f"({day['water_amount']}L)" if day["needs_irrigation"] else ""
        print(f"   {day['date']} {day['weekday']}: 湿度{day['soil_moisture']}% {status} {water}")

    # 5. 水资源优化
    print("\n📍 测试5: 水资源优化 (预算500L)")
    optimization = planner.optimize_water_usage(500, crops, soil)
    print(f"   消息: {optimization['message']}")
    for alloc in optimization["allocation"]:
        full = "完整" if alloc.get("full") else f"部分({alloc.get('ratio', 0):.0%})"
        print(f"   - {alloc['crop']}: {alloc['water']}L [{full}]")

    print("\n" + "=" * 50)
    print("✅ 测试完成!")
