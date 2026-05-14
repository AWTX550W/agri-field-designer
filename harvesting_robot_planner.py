# -*- coding: utf-8 -*-
"""
智能采摘机器人规划器 - AI视觉+机械臂协同
目标识别 + 采摘路径优化 + 抓取策略
新增：农民作业路径预测（规避/协同）
"""

import numpy as np
import math
import sys
import json
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

@dataclass
class FruitTarget:
    """果实目标数据结构"""
    x: float      # 相对机器人坐标 X (m)
    y: float      # 相对机器人坐标 Y (m)
    z: float      # 高度 (m)
    radius: float # 果实半径 (m)
    maturity: float  # 成熟度 0-1
    priority: int = 1  # 采摘优先级

@dataclass
class PredictedPath:
    """预测路径数据结构"""
    next_position: Tuple[float, float]  # 预测的下一点 (x, y)
    direction: Tuple[float, float]      # 方向向量 (dx, dy)
    confidence: float                   # 预测置信度 0-1
    speed: float                         # 估计速度 (m/s)

class FarmerPathPredictor:
    """
    农民作业路径预测器
    读取GPS轨迹，预测下一步移动方向，用于机器人规避或协同
    """
    
    def __init__(self, window_size: int = 5):
        """
        :param window_size: 用于预测的历史窗口大小
        """
        self.window_size = window_size
        self.gps_points = []  # 原始GPS点 [(lat, lon, timestamp), ...]
        self.local_points = []  # 局部坐标点 [(x, y, timestamp), ...]
        self.reference_point = None  # 参考点 (lat0, lon0) 用于坐标转换
        
    def load_gps_trace(self, file_path: str) -> bool:
        """
        从JSONL文件加载GPS轨迹
        :param file_path: GPS轨迹文件路径
        :return: 是否加载成功
        """
        try:
            path = Path(file_path)
            if not path.exists():
                print(f"❌ 文件不存在: {file_path}")
                return False
            
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self.gps_points.append((
                        data['latitude'],
                        data['longitude'],
                        data.get('altitude', 0.0),
                        data['timestamp']
                    ))
            
            if len(self.gps_points) < 2:
                print(f"⚠️  GPS轨迹点数不足: {len(self.gps_points)}")
                return False
            
            # 设置参考点（第一个点）
            self.reference_point = (self.gps_points[0][0], self.gps_points[0][1])
            
            # 转换为局部坐标
            self._convert_to_local()
            
            print(f"✅ 已加载 {len(self.gps_points)} 个GPS轨迹点")
            return True
            
        except Exception as e:
            print(f"❌ 加载GPS轨迹失败: {e}")
            return False
    
    def _convert_to_local(self):
        """将GPS经纬度转换为局部直角坐标系（简化等距投影）"""
        if not self.reference_point:
            return
        
        lat0, lon0 = self.reference_point
        # 等距圆柱投影（适合小范围）
        # 1度纬度 ≈ 111320米，1度经度 ≈ 111320*cos(lat0) 米
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * math.cos(math.radians(lat0))
        
        self.local_points = []
        for lat, lon, alt, ts in self.gps_points:
            x = (lon - lon0) * meters_per_deg_lon
            y = (lat - lat0) * meters_per_deg_lat
            self.local_points.append((x, y, ts))
    
    def predict_next_position(self, n_points: Optional[int] = None) -> Optional[PredictedPath]:
        """
        预测下一个位置
        使用线性回归拟合最近n个点的运动趋势
        :param n_points: 使用的历史点数，默认使用window_size
        :return: 预测路径对象
        """
        if len(self.local_points) < 2:
            return None
        
        n = n_points or self.window_size
        n = min(n, len(self.local_points))
        
        # 取最近n个点
        recent_points = self.local_points[-n:]
        
        # 简单线性回归: x = a*t + b, y = c*t + d
        # 使用序号作为时间变量（假设均匀采样）
        t = np.arange(len(recent_points))
        x = np.array([p[0] for p in recent_points])
        y = np.array([p[1] for p in recent_points])
        
        # 线性回归
        coeff_x = np.polyfit(t, x, 1)
        coeff_y = np.polyfit(t, y, 1)
        
        # 预测下一个位置 (t = n)
        t_next = float(n)
        x_next = float(np.polyval(coeff_x, t_next))
        y_next = float(np.polyval(coeff_y, t_next))
        
        # 计算方向向量
        dx = float(coeff_x[0])  # 每时间单位的x变化
        dy = float(coeff_y[0])  # 每时间单位的y变化
        
        # 归一化方向向量
        norm = math.sqrt(dx**2 + dy**2)
        if norm > 0:
            dx_norm = dx / norm
            dy_norm = dy / norm
        else:
            dx_norm = 0
            dy_norm = 0
        
        # 计算置信度（基于拟合误差）
        x_pred = np.polyval(coeff_x, t)
        y_pred = np.polyval(coeff_y, t)
        residuals_x = x - x_pred
        residuals_y = y - y_pred
        mse = np.mean(residuals_x**2 + residuals_y**2)
        
        # 置信度 = 1 / (1 + mse)，误差越小置信度越高
        confidence = 1.0 / (1.0 + mse / 100.0)  # 归一化到0-1
        
        # 估计速度（假设时间间隔均匀）
        if len(recent_points) >= 2:
            # 计算最近两点间的距离和时间差
            x1, y1, t1 = recent_points[-2][0], recent_points[-2][1], recent_points[-2][2]
            x2, y2, t2 = recent_points[-1][0], recent_points[-1][1], recent_points[-1][2]
            dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            
            # 解析时间戳（假设ISO格式）
            try:
                from datetime import datetime
                ts1 = datetime.fromisoformat(t1.replace('Z', '+00:00'))
                ts2 = datetime.fromisoformat(t2.replace('Z', '+00:00'))
                dt = abs((ts2 - ts1).total_seconds())
                
                # 如果时间差太小，使用平均移动速度估算
                if dt < 0.001:  # 小于1毫秒，认为数据有问题
                    # 降级：假设典型农业机器人速度 0.3-1.0 m/s
                    speed = 0.5
                else:
                    speed = dist / dt
                    # 限制合理范围（农业作业：0.1-2.0 m/s）
                    speed = max(0.1, min(2.0, speed))
            except:
                # 解析失败，使用默认值
                speed = 0.5
        else:
            speed = 0.5  # 默认速度
        
        return PredictedPath(
            next_position=(x_next, y_next),
            direction=(dx_norm, dy_norm),
            confidence=confidence,
            speed=speed
        )
    
    def check_collision_risk(self, robot_pos: Tuple[float, float], 
                            safe_distance: float = 5.0) -> Tuple[bool, float]:
        """
        检查农民与机器人是否存在碰撞风险
        :param robot_pos: 机器人位置 (x, y)
        :param safe_distance: 安全距离 (m)
        :return: (是否存在风险, 预计碰撞时间)
        """
        prediction = self.predict_next_position()
        if not prediction:
            return False, float('inf')
        
        # 计算农民预测位置与机器人的距离
        farmer_next = prediction.next_position
        dist = math.sqrt((farmer_next[0] - robot_pos[0])**2 + 
                         (farmer_next[1] - robot_pos[1])**2)
        
        if dist < safe_distance:
            # 估算碰撞时间
            relative_speed = prediction.speed
            if relative_speed > 0:
                ttc = dist / relative_speed
            else:
                ttc = float('inf')
            return True, ttc
        
        return False, float('inf')
    
    def get_farmer_current_position(self) -> Optional[Tuple[float, float]]:
        """获取农民当前位置（最后一个GPS点）"""
        if not self.local_points:
            return None
        return (self.local_points[-1][0], self.local_points[-1][1])
    
    def visualize_farmer_path(self) -> dict:
        """生成农民路径可视化数据"""
        if not self.local_points:
            return {}
        
        return {
            "gps_points": [(p[0], p[1]) for p in self.local_points],
            "current_position": self.get_farmer_current_position(),
            "prediction": self.predict_next_position()
        }

class HarvestingPlanner:
    """采摘机器人路径规划器"""

    def __init__(self, arm_reach: float = 1.2, speed: float = 0.3, 
                 farmer_predictor: Optional[FarmerPathPredictor] = None):
        """
        :param arm_reach: 机械臂最大伸展半径 (m)
        :param speed: 机器人移动速度 (m/s)
        :param farmer_predictor: 农民路径预测器（可选）
        """
        self.arm_reach = arm_reach
        self.speed = speed
        self.farmer_predictor = farmer_predictor
        self.safe_distance = 5.0  # 与农民的安全距离

    def detect_targets(self, vision_data: List[dict]) -> List[FruitTarget]:
        """
        从视觉检测结果生成目标列表
        :param vision_data: 视觉检测输出 [{"x":..., "y":..., "z":..., "maturity":...}, ...]
        :return: 排序后的采摘目标列表
        """
        targets = []
        for item in vision_data:
            target = FruitTarget(
                x=item["x"],
                y=item["y"],
                z=item.get("z", 0.5),  # 默认高度0.5m
                radius=item.get("radius", 0.05),
                maturity=item["maturity"],
                priority=self._calc_priority(item)
            )
            targets.append(target)

        # 按优先级+距离综合排序
        targets.sort(key=lambda t: (t.priority, math.sqrt(t.x**2 + t.y**2)))
        return targets

    def _calc_priority(self, target: dict) -> int:
        """计算采摘优先级"""
        maturity = target["maturity"]
        if maturity >= 0.9:
            return 1   # 立即采摘
        elif maturity >= 0.7:
            return 2   # 优先采摘
        else:
            return 3   # 稍后采摘

    def plan_route(self, targets: List[FruitTarget], start_pos: Tuple[float, float] = (0, 0)) -> List[dict]:
        """
        规划机器人移动+机械臂采摘的完整路径
        :return: 动作序列 [{"action": "move"|"pick", "target": ..., "duration": ...}, ...]
        """
        actions = []
        current_pos = np.array(start_pos, dtype=float)

        for target in targets:
            # 计算目标点相对位置
            target_pos = np.array([target.x, target.y])
            distance = np.linalg.norm(target_pos - current_pos)

            # 判断是否需要移动机器人
            if distance > self.arm_reach * 0.8:  # 留安全余量
                # 移动到最佳采摘位置（机械臂伸展最优位置）
                move_dist = distance - self.arm_reach * 0.7
                direction = (target_pos - current_pos) / distance
                optimal_pos = target_pos - direction * (self.arm_reach * 0.7)

                actions.append({
                    "action": "move",
                    "from": (float(current_pos[0]), float(current_pos[1])),
                    "to": (float(optimal_pos[0]), float(optimal_pos[1])),
                    "distance": round(float(move_dist), 2),
                    "duration": round(float(move_dist / self.speed), 1)
                })
                current_pos = optimal_pos

            # 添加采摘动作
            actions.append({
                "action": "pick",
                "target": (float(target.x), float(target.y), float(target.z)),
                "maturity": float(target.maturity),
                "priority": int(target.priority),
                "duration": 3.0  # 单次采摘耗时约3秒
            })

        return actions

    def plan_route_with_avoidance(self, targets: List[FruitTarget], 
                                   start_pos: Tuple[float, float] = (0, 0),
                                   safe_distance: float = 5.0) -> List[dict]:
        """
        带农民避障的路径规划
        考虑农民预测路径，动态调整机器人路径
        :param safe_distance: 与农民的安全距离 (m)
        :return: 动作序列（可能包含等待动作）
        """
        if not self.farmer_predictor:
            print("⚠️  未配置农民路径预测器，使用普通路径规划")
            return self.plan_route(targets, start_pos)
        
        actions = []
        current_pos = np.array(start_pos, dtype=float)
        
        for target in targets:
            target_pos = np.array([target.x, target.y], dtype=float)
            distance = np.linalg.norm(target_pos - current_pos)
            
            # 检查移动到目标位置是否安全
            if distance > self.arm_reach * 0.8:
                move_dist = distance - self.arm_reach * 0.7
                direction = (target_pos - current_pos) / distance
                optimal_pos = target_pos - direction * (self.arm_reach * 0.7)
                
                # 检查此位置是否与农民有碰撞风险
                has_risk, ttc = self.farmer_predictor.check_collision_risk(
                    (float(optimal_pos[0]), float(optimal_pos[1])), safe_distance
                )
                
                if has_risk:
                    # 策略1：等待农民通过
                    print(f"⚠️  检测到碰撞风险！预计碰撞时间: {ttc:.1f}s")
                    wait_time = ttc + 2.0  # 额外2秒安全余量
                    actions.append({
                        "action": "wait",
                        "duration": round(wait_time, 1),
                        "reason": "农民路径冲突"
                    })
                
                actions.append({
                    "action": "move",
                    "from": (float(current_pos[0]), float(current_pos[1])),
                    "to": (float(optimal_pos[0]), float(optimal_pos[1])),
                    "distance": round(float(move_dist), 2),
                    "duration": round(float(move_dist / self.speed), 1),
                    "safe_distance_maintained": safe_distance
                })
                current_pos = optimal_pos
            
            # 添加采摘动作
            actions.append({
                "action": "pick",
                "target": (float(target.x), float(target.y), float(target.z)),
                "maturity": float(target.maturity),
                "priority": int(target.priority),
                "duration": 3.0
            })
        
        return actions

    def get_safety_status(self, robot_pos: Tuple[float, float]) -> dict:
        """
        获取当前安全状态
        :param robot_pos: 机器人当前位置
        :return: 安全状态字典
        """
        if not self.farmer_predictor:
            return {"status": "unknown", "message": "未配置农民路径预测器"}
        
        farmer_pos = self.farmer_predictor.get_farmer_current_position()
        if not farmer_pos:
            return {"status": "unknown", "message": "无法获取农民位置"}
        
        dist = math.sqrt((robot_pos[0] - farmer_pos[0])**2 + 
                         (robot_pos[1] - farmer_pos[1])**2)
        
        prediction = self.farmer_predictor.predict_next_position()
        
        if dist < self.safe_distance:
            status = "danger"
            message = f"距离农民过近: {dist:.1f}m"
        elif prediction and dist < self.safe_distance * 2:
            status = "warning"
            message = f"预测路径可能接近: {dist:.1f}m"
        else:
            status = "safe"
            message = f"安全距离: {dist:.1f}m"
        
        return {
            "status": status,
            "message": message,
            "distance": round(dist, 2),
            "farmer_position": farmer_pos,
            "prediction": prediction
        }

    def estimate_harvest_time(self, actions: List[dict]) -> dict:
        """估算总耗时"""
        move_time = sum(a["duration"] for a in actions if a["action"] == "move")
        pick_time = sum(a["duration"] for a in actions if a["action"] == "pick")
        total_time = move_time + pick_time

        return {
            "移动时间(s)": round(move_time, 1),
            "采摘时间(s)": round(pick_time, 1),
            "总时间(s)": round(total_time, 1),
            "采摘数量": len([a for a in actions if a["action"] == "pick"]),
            "平均单果时间(s)": round(total_time / len([a for a in actions if a["action"] == "pick"]), 1)
        }

    def simulate_visualization(self, targets: List[FruitTarget], actions: List[dict]):
        """生成可视化数据（供前端/仿真使用）"""
        viz = {
            "targets": [
                {
                    "x": float(t.x), 
                    "y": float(t.y), 
                    "z": float(t.z), 
                    "maturity": float(t.maturity), 
                    "priority": int(t.priority)
                }
                for t in targets
            ],
            "robot_path": [
                {
                    "x": float(a["to"][0]) if a["action"] == "move" else float(a["target"][0]),
                    "y": float(a["to"][1]) if a["action"] == "move" else float(a["target"][1]),
                    "action": a["action"]
                }
                for a in actions
            ],
            "stats": self.estimate_harvest_time(actions)
        }
        return viz


# ============ 示例用法 ============

if __name__ == "__main__":
    print("🤖 智能采摘机器人规划器已就绪\n")
    
    # 1. 农民路径预测演示
    print("=" * 60)
    print("📍 农民作业路径预测演示")
    print("=" * 60 + "\n")
    
    # 创建路径预测器
    predictor = FarmerPathPredictor(window_size=5)
    
    # 加载GPS轨迹（如果存在）
    gps_file = "gps_trace.json"
    if predictor.load_gps_trace(gps_file):
        # 预测下一步位置
        prediction = predictor.predict_next_position()
        if prediction:
            print(f"✅ 路径预测结果:")
            print(f"   预测下一点: {prediction.next_position}")
            print(f"   移动方向: ({prediction.direction[0]:.3f}, {prediction.direction[1]:.3f})")
            print(f"   预测置信度: {prediction.confidence:.2%}")
            print(f"   估计速度: {prediction.speed:.2f} m/s")
        
        # 显示农民当前位置
        current = predictor.get_farmer_current_position()
        if current:
            print(f"\n📍 农民当前位置: ({current[0]:.2f}m, {current[1]:.2f}m)")
        
        # 检查与机器人的碰撞风险
        robot_pos = (50.0, 50.0)  # 假设机器人位置
        has_risk, ttc = predictor.check_collision_risk(robot_pos, safe_distance=10.0)
        if has_risk:
            print(f"\n⚠️  碰撞风险警告！预计碰撞时间: {ttc:.1f}秒")
        else:
            print(f"\n✅ 与机器人位置 {robot_pos} 安全距离充足")
    else:
        print(f"⚠️  无法加载GPS轨迹文件: {gps_file}")
        print("   将使用模拟数据进行演示\n")
    
    print("\n" + "=" * 60)
    print("🍎 采摘路径规划演示")
    print("=" * 60 + "\n")
    
    # 2. 采摘路径规划演示
    # 模拟视觉检测数据（实际应从摄像头+YOLO等模型获取）
    simulated_vision = [
        {"x": 2.5, "y": 1.2, "z": 0.6, "radius": 0.05, "maturity": 0.95},   # 高度成熟
        {"x": 3.0, "y": 1.5, "z": 0.55, "radius": 0.04, "maturity": 0.85},  # 成熟
        {"x": 1.8, "y": 0.8, "z": 0.65, "radius": 0.06, "maturity": 0.92},  # 高度成熟
        {"x": 4.2, "y": 2.1, "z": 0.58, "radius": 0.05, "maturity": 0.65},  # 半成熟
        {"x": 5.0, "y": 2.5, "z": 0.62, "radius": 0.05, "maturity": 0.98},  # 极熟
    ]
    
    # 创建规划器（带农民路径预测器）
    planner = HarvestingPlanner(
        arm_reach=1.2, 
        speed=0.3,
        farmer_predictor=predictor if predictor.gps_points else None
    )
    
    # 步骤1: 目标检测与排序
    print("🔍 目标检测与优先级排序:")
    targets = planner.detect_targets(simulated_vision)
    for i, t in enumerate(targets, 1):
        print(f"   目标{i}: 位置({t.x:.1f},{t.y:.1f},{t.z:.2f}) 成熟度{t.maturity:.0%} 优先级{t.priority}")
    
    # 步骤2: 路径规划（带避障）
    if planner.farmer_predictor:
        print("\n🗺️  路径规划（带农民避障）:")
        actions = planner.plan_route_with_avoidance(targets, start_pos=(0, 0))
    else:
        print("\n🗺️  路径规划（标准模式）:")
        actions = planner.plan_route(targets, start_pos=(0, 0))
    
    for i, a in enumerate(actions, 1):
        if a["action"] == "wait":
            print(f"   动作{i}: ⏸️  等待 {a['duration']}秒 ({a['reason']})")
        elif a["action"] == "move":
            print(f"   动作{i}: 移动 from {a['from']} → to {a['to']} (距离{a['distance']}m, 耗时{a['duration']}s)")
        else:
            print(f"   动作{i}: 采摘 位置{a['target']} 成熟度{a['maturity']:.0%} (耗时{a['duration']}s)")
    
    # 步骤3: 耗时统计
    print("\n⏱️  效率统计:")
    stats = planner.estimate_harvest_time(actions)
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    # 步骤4: 安全状态检查
    if planner.farmer_predictor:
        print("\n🛡️  安全状态:")
        safety = planner.get_safety_status((0, 0))
        print(f"   状态: {safety['status']}")
        print(f"   信息: {safety['message']}")
    
    # 步骤5: 输出可视化数据
    print("\n📊 可视化数据（可对接前端/仿真）:")
    viz = planner.simulate_visualization(targets, actions)
    print(f"   目标点数量: {len(viz['targets'])}")
    print(f"   路径点数量: {len(viz['robot_path'])}")
    print(f"   预计总耗时: {viz['stats']['总时间(s)']}秒")
    
    print("\n💡 扩展方向:")
    print("   1. 对接YOLO/Detectron2等成熟检测模型")
    print("   2. 加入避障算法（动态障碍物）")
    print("   3. 多机协同采摘（任务分配）")
    print("   4. 机械臂逆运动学求解（具体抓取姿态）")
    print("   5. 实时GPS数据流接入（WebSocket/MQTT）")
    print("   6. 农民-机器人协同作业策略优化")
