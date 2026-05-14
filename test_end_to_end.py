# -*- coding: utf-8 -*-
"""
端到端集成测试 - 采摘机器人全链路验证
数据生成 → GPS轨迹加载 → 农民路径预测 → 视觉目标检测 → 采摘路径规划(带避障) → 统计输出

用法:
    python test_end_to_end.py          # 运行完整集成测试
    python test_end_to_end.py --viz     # 运行 + 输出可视化JSON
"""

import sys
import os
import json
import math
import traceback
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path 中
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# ============ 导入项目模块 ============
from real_data_interface import (
    GPSDataSource, CameraDataSource, SensorDataSource,
    DataFuser, create_gps_trace_file, GPSPosition
)
from harvesting_robot_planner import (
    HarvestingPlanner, FarmerPathPredictor, FruitTarget, PredictedPath
)


# ============ 测试工具 ============

class TestResult:
    """简单的测试结果收集器"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list = []
        self.results: list = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        self.results.append({"status": "PASS", "test": name, "detail": detail})
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        self.errors.append(name)
        self.results.append({"status": "FAIL", "test": name, "detail": detail})
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"📊 测试结果: {self.passed}/{total} 通过")
        if self.failed:
            print(f"   失败: {', '.join(self.errors)}")
        print(f"{'='*60}")
        return self.failed == 0


def assert_eq(test: TestResult, name: str, actual, expected, tol=0):
    """数值/值相等断言"""
    if isinstance(actual, float) and isinstance(expected, float) and tol > 0:
        ok = abs(actual - expected) <= tol
    else:
        ok = actual == expected
    if ok:
        test.ok(name, f"实际={actual}")
    else:
        test.fail(name, f"期望={expected}, 实际={actual}")


def assert_true(test: TestResult, name: str, condition, detail=""):
    """布尔断言"""
    if condition:
        test.ok(name, detail)
    else:
        test.fail(name, detail)


# ============ 集成测试主流程 ============

def run_integration_test(output_viz=False, explain=False):
    """
    完整的端到端集成测试

    流程:
      1. 生成GPS轨迹测试数据
      2. FarmerPathPredictor 加载轨迹并预测
      3. HarvestingPlanner 检测目标 + 规划路径（带避障）
      4. 效率统计与安全状态检查
      5. 断言验证各环节输出正确性
    """
    test = TestResult()
    viz_data = {"timestamp": datetime.now().isoformat(), "stages": {}}

    print("\n" + "🌾" * 30)
    print("  采摘机器人端到端集成测试")
    print("🌾" * 30 + "\n")

    # ========================================
    # Stage 1: 数据准备 - 生成GPS轨迹
    # ========================================
    print("▶ Stage 1: 数据准备 — 生成GPS轨迹")

    trace_file = SCRIPT_DIR / "test_gps_trace.json"
    try:
        create_gps_trace_file(str(trace_file), num_points=20)
        assert_true(test, "GPS轨迹文件生成", trace_file.exists(), f"路径={trace_file}")
        viz_data["stages"]["data_prep"] = {"trace_file": str(trace_file), "points": 20}
    except Exception as e:
        test.fail("GPS轨迹文件生成", str(e))
        return test, viz_data

    # ========================================
    # Stage 2: 路径预测 - FarmerPathPredictor
    # ========================================
    print("\n▶ Stage 2: 农民路径预测")

    predictor = None
    try:
        predictor = FarmerPathPredictor(window_size=5)
        loaded = predictor.load_gps_trace(str(trace_file))
        assert_true(test, "GPS轨迹加载成功", loaded)

        prediction = predictor.predict_next_position()
        assert_true(test, "路径预测返回结果", prediction is not None)
        
        if prediction:
            # 验证预测结果的合理性
            assert_true(test, "预测位置是元组", isinstance(prediction.next_position, tuple))
            assert_true(test, "方向向量已归一化",
                       math.isclose(
                           math.sqrt(prediction.direction[0]**2 + prediction.direction[1]**2),
                           1.0, abs_tol=0.01
                       ) or 
                       (prediction.direction[0] == 0 and prediction.direction[1] == 0),
                       f"direction=({prediction.direction[0]:.3f}, {prediction.direction[1]:.3f})")
            assert_true(test, "置信度在0-1范围", 0 <= prediction.confidence <= 1,
                       f"confidence={prediction.confidence:.2%}")
            assert_true(test, "速度在合理范围(0.1-2.0 m/s)", 0.1 <= prediction.speed <= 2.0,
                       f"speed={prediction.speed:.2f} m/s")
            
            print(f"   📍 预测下一点: ({prediction.next_position[0]:.2f}, {prediction.next_position[1]:.2f})")
            print(f"   🔢 方向: ({prediction.direction[0]:.3f}, {prediction.direction[1]:.3f})")
            print(f"   📈 置信度: {prediction.confidence:.1%} | 速度: {prediction.speed:.2f} m/s")

            viz_data["stages"]["path_prediction"] = {
                "next_position": prediction.next_position,
                "direction": prediction.direction,
                "confidence": round(prediction.confidence, 4),
                "speed": prediction.speed,
                "current_position": predictor.get_farmer_current_position()
            }

        # 测试碰撞检测
        has_risk, ttc = predictor.check_collision_risk((99999, 99999), safe_distance=5.0)
        assert_true(test, "远距离无碰撞风险", not has_risk, f"ttc={ttc}")

        has_risk_close, ttc_close = predictor.check_collision_risk(
            predictor.get_farmer_current_position() or (0, 0), safe_distance=10000.0
        )
        assert_true(test, "近距离有碰撞风险", has_risk_close, f"ttc={ttc_close:.1f}s")

    except Exception as e:
        test.fail("路径预测异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()

    # ========================================
    # Stage 3: 目标检测 + 路径规划
    # ========================================
    print("\n▶ Stage 3: 目标检测 & 采摘路径规划")

    planner = None
    actions = []
    targets = []

    try:
        # 模拟视觉检测结果（模拟YOLO/检测模型输出）
        simulated_vision = [
            {"x": 2.5, "y": 1.2, "z": 0.6, "radius": 0.05, "maturity": 0.95},
            {"x": 3.0, "y": 1.5, "z": 0.55, "radius": 0.04, "maturity": 0.85},
            {"x": 1.8, "y": 0.8, "z": 0.65, "radius": 0.06, "maturity": 0.92},
            {"x": 4.2, "y": 2.1, "z": 0.58, "radius": 0.05, "maturity": 0.65},
            {"x": 5.0, "y": 2.5, "z": 0.62, "radius": 0.05, "maturity": 0.98},
            {"x": 0.5, "y": 3.0, "z": 0.50, "radius": 0.04, "maturity": 0.75},
            {"x": 3.5, "y": 0.3, "z": 0.70, "radius": 0.07, "maturity": 0.88},
        ]

        # 创建规划器（接入农民路径预测器）
        planner = HarvestingPlanner(
            arm_reach=1.2,
            speed=0.3,
            farmer_predictor=predictor
        )

        # 步骤A: 目标检测
        targets = planner.detect_targets(simulated_vision)
        assert_eq(test, "检测到7个目标", len(targets), 7)
        assert_true(test, "目标按优先级排序",
                   all(targets[i].priority <= targets[i+1].priority for i in range(len(targets)-1)),
                   f"优先级序列: {[t.priority for t in targets]}")

        print(f"   🔍 检测到 {len(targets)} 个果实目标:")
        for i, t in enumerate(targets, 1):
            print(f"      #{i} 位置({t.x:.1f},{t.y:.1f}) 成熟度{t.maturity:.0%} 优先级{t.priority}")

        # 创建位置->目标信息的映射（用于--explain）
        target_info = {}
        for i, t in enumerate(targets, 1):
            target_info[(round(t.x, 2), round(t.y, 2))] = {
                "index": i,
                "priority": t.priority,
                "maturity": t.maturity
            }

        # 步骤B: 带避障的路径规划
        actions = planner.plan_route_with_avoidance(targets, start_pos=(0, 0), safe_distance=5.0)
        assert_true(test, "路径规划产出动作序列", len(actions) > 0, f"共{len(actions)}个动作")

        move_count = sum(1 for a in actions if a["action"] == "move")
        pick_count = sum(1 for a in actions if a["action"] == "pick")
        wait_count = sum(1 for a in actions if a["action"] == "wait")

        assert_eq(test, "采摘动作数量=目标数", pick_count, len(targets))
        assert_true(test, "存在移动动作", move_count > 0, f"move={move_count}")

        print(f"   🗺️  路径规划完成:")
        print(f"      移动: {move_count}次 | 采摘: {pick_count}个 | 等待: {wait_count}次")

        for i, a in enumerate(actions, 1):
            if a["action"] == "wait":
                print(f"      #{i} ⏸️  等待 {a['duration']}s ({a.get('reason', '')})")
            elif a["action"] == "move":
                print(f"      #{i} ➡️  {a['from']} → {a['to']} ({a['distance']}m, {a['duration']}s)")
            else:
                print(f"      #{i} 🍎  @{a['target'][:2]} 成熟度{a['maturity']:.0%}")
                if explain:
                    pos = (round(a['target'][0], 2), round(a['target'][1], 2))
                    info = target_info.get(pos)
                    if info:
                        idx = info["index"]
                        mat = info["maturity"]
                        pri = info["priority"]
                        if pri == 1:
                            reason = "成熟度最高，优先采摘"
                        elif pri == 2:
                            reason = "成熟度中等，次优先采摘"
                        else:
                            reason = "成熟度较低，最后采摘"
                        print(f"         📝 解释：果实#{idx}成熟度{mat:.0%}，{reason}")
                    else:
                        print(f"         📝 解释：成熟度{a['maturity']:.0%}")

        viz_data["stages"]["detection_planning"] = {
            "targets_detected": len(targets),
            "actions_total": len(actions),
            "actions_breakdown": {"move": move_count, "pick": pick_count, "wait": wait_count}
        }

    except Exception as e:
        test.fail("目标检测/路径规划异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()

    # ========================================
    # Stage 4: 效率统计
    # ========================================
    print("\n▶ Stage 4: 效率统计")

    try:
        if planner and actions:
            stats = planner.estimate_harvest_time(actions)
            
            assert_true(test, "总时间>0", stats["总时间(s)"] > 0, f"总时间={stats['总时间(s)']}")
            assert_true(test, "采摘数量正确", stats["采摘数量"] == len(targets),
                       f"采摘数={stats['采摘数量']}, 目标数={len(targets)}")
            assert_true(test, "平均单果时间合理",
                       1 <= stats["平均单果时间(s)"] <= 30,
                       f"平均={stats['平均单果时间(s)']:.1f}s")

            print(f"   ⏱️  效率指标:")
            for k, v in stats.items():
                print(f"      {k}: {v}")

            viz_data["stages"]["efficiency_stats"] = stats

    except Exception as e:
        test.fail("效率统计异常", f"{type(e).__name__}: {e}")

    # ========================================
    # Stage 5: 安全状态检查
    # ========================================
    print("\n▶ Stage 5: 安全状态检查")

    try:
        if planner and planner.farmer_predictor:
            safety = planner.get_safety_status((0, 0))
            assert_true(test, "安全状态返回有效字典", isinstance(safety, dict) and "status" in safety)
            assert_true(test, "安全状态为已知值", safety["status"] in ("safe", "warning", "danger"),
                       f"status={safety['status']}")
            assert_true(test, "包含距离信息", "distance" in safety and safety["distance"] >= 0,
                       f"distance={safety.get('distance')}")

            emoji = {"safe": "✅", "warning": "⚠️", "danger": "🚨"}.get(safety["status"], "❓")
            print(f"   🛡️  状态: {emoji} {safety['status']} | {safety['message']}")
            print(f"      与农民距离: {safety.get('distance', '?'):.1f}m")

            viz_data["stages"]["safety_check"] = {
                "status": safety["status"],
                "message": safety["message"],
                "distance": safety.get("distance")
            }

    except Exception as e:
        test.fail("安全状态异常", f"{type(e).__name__}: {e}")

    # ========================================
    # Stage 6: 可视化数据导出
    # ========================================
    if output_viz and planner and targets and actions:
        print("\n▶ Stage 6: 导出可视化数据")
        try:
            viz = planner.simulate_visualization(targets, actions)
            viz_path = SCRIPT_DIR / "test_viz_output.json"
            with open(viz_path, 'w', encoding='utf-8') as f:
                json.dump(viz, f, ensure_ascii=False, indent=2)
            assert_true(test, "可视化JSON已导出", viz_path.exists())
            print(f"   📊 已保存: {viz_path.name}")
            viz_data["visualization"] = viz
        except Exception as e:
            test.fail("可视化导出异常", str(e))

    # ========================================
    # 最终结论
    # ========================================
    all_ok = test.summary()

    if all_ok:
        print("\n🎉 全链路验证通过！采摘机器人系统各模块协作正常。")
        print("   数据层(real_data_interface) → 规划层(harvesting_planner) → 输出统计 ✓\n")
    else:
        print("\n⚠️  部分测试未通过，请检查上述 FAIL 项。\n")

    return test, viz_data


if __name__ == "__main__":
    output_viz = "--viz" in sys.argv
    output_explain = "--explain" in sys.argv

    # 运行测试
    test_result, viz = run_integration_test(output_viz=output_viz, explain=output_explain)
    
    # 以退出码反映测试结果（0=全部通过，1=有失败）
    sys.exit(0 if test_result.failed == 0 else 1)
