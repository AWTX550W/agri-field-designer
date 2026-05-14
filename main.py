#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
农机自动驾驶路径规划系统 - 主程序
功能: 串联所有模块，提供完整路径规划流程
作者: 农业机械化工程专业校招展示
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run_full_pipeline(working_width=5.0, field_type='rectangle'):
    """运行完整流程"""
    print("="*60)
    print("农机自动驾驶路径规划 - 完整流程")
    print("="*60)
    
    if field_type == 'rectangle':
        boundary = [(0, 0), (100, 0), (100, 60), (0, 60)]
    elif field_type == 'l_shape':
        boundary = [(0, 0), (60, 0), (60, 30), (30, 30), (30, 60), (0, 60)]
    elif field_type == 'irregular':
        boundary = [(0, 0), (80, 5), (100, 20), (90, 50), (70, 55), (50, 80), (20, 70), (5, 40)]
    else:
        boundary = [(0, 0), (100, 0), (100, 60), (0, 60)]
    
    obstacles = [((50, 30), 8)]
    
    # Step 1: 基础路径规划
    print("\n[Step 1/4] 基础弓字形路径规划")
    print("-"*40)
    from modules.base_planner import FieldPlanner
    
    base = FieldPlanner(working_width=working_width)
    base.load_field(boundary)
    base.load_obstacles(obstacles)
    base.generate_work_lines()
    base.generate_zigzag()
    stats = base.get_stats()
    
    print(f"\n统计: 作业线{stats.work_lines}条, 总路径{stats.total_length}m, 覆盖率{stats.coverage_rate}%")
    base.visualize(f"output/step1_base_{field_type}.png")
    print(f"可视化: output/step1_base_{field_type}.png")
    
    # Step 2: 动态避障
    print("\n[Step 2/4] 动态障碍物避障 (D* Lite)")
    print("-"*40)
    from modules.dynamic_avoidance import DynamicObstacleplanner
    
    planner = DynamicObstacleplanner(base)
    path = planner.plan((10, 5), (90, 55), [(50, 30, 8)])
    print(f"规划路径点: {len(path)} 个")
    planner.visualize_comparison(f"output/step2_dynamic_{field_type}.png")
    print(f"可视化: output/step2_dynamic_{field_type}.png")
    
    # Step 3: 路径平滑
    print("\n[Step 3/4] B样条路径平滑")
    print("-"*40)
    from modules.path_smoothing import BSplineSmoother
    
    smoother = BSplineSmoother(max_curvature=0.15, max_steering_angle=30)
    smoothed, curvatures, headings = smoother.smooth(base.path, num_samples=300)
    print(f"平滑后: {len(smoothed)} 点, 最大曲率{max(curvatures):.4f}")
    smoother.visualize(base.path, smoothed, curvatures, headings, f"output/step3_smooth_{field_type}.png")
    print(f"可视化: output/step3_smooth_{field_type}.png")
    
    # Step 4: 多机协同
    print("\n[Step 4/4] 多机协同作业规划")
    print("-"*40)
    from modules.multi_robot import MultiRobotPlanner
    
    num_robots = 3
    multi = MultiRobotPlanner(boundary, num_robots=num_robots, working_width=working_width)
    multi.assign_work_lines()
    multi.plan_paths()
    collisions = multi.check_collisions()
    if collisions:
        multi.resolve_collisions()
    
    stats = multi.get_statistics()
    print(f"农机{num_robots}台, 作业线{stats['total_lines']}条")
    for r in stats['robots']:
        print(f"  Robot {r['id']}: {r['assigned_lines']}条线, {r['path_length']}m")
    
    multi.visualize(f"output/step4_multi_{field_type}.png")
    print(f"可视化: output/step4_multi_{field_type}.png")
    
    print("\n" + "="*60)
    print("流程完成！")
    print("="*60)


def run_web_server(port=5000):
    """启动Web服务"""
    from web.app import app
    print("="*50)
    print("农机路径规划 Web 可视化系统")
    print(f"访问地址: http://localhost:{port}")
    print("="*50)
    app.run(host='0.0.0.0', port=port, debug=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='农机自动驾驶路径规划系统')
    parser.add_argument('--full', action='store_true', help='运行完整流程')
    parser.add_argument('--web', action='store_true', help='启动Web服务')
    parser.add_argument('--test', choices=['base', 'dynamic', 'smooth', 'multi'], help='测试单个模块')
    parser.add_argument('--field', choices=['rectangle', 'l_shape', 'irregular'], default='rectangle', help='田块类型')
    parser.add_argument('--width', type=float, default=5.0, help='作业幅宽(m)')
    parser.add_argument('--port', type=int, default=5000, help='Web服务端口')
    
    args = parser.parse_args()
    
    Path('output').mkdir(exist_ok=True)
    
    if args.test:
        if args.test == 'base':
            from modules.base_planner import FieldPlanner
            p = FieldPlanner(working_width=args.width)
            p.load_field([(0,0), (100,0), (100,60), (0,60)])
            p.generate_work_lines()
            p.generate_zigzag()
            p.visualize('output/test_base.png')
            print("Done: output/test_base.png")
        elif args.test == 'dynamic':
            from modules.base_planner import FieldPlanner
            from modules.dynamic_avoidance import DynamicObstacleplanner
            base = FieldPlanner(working_width=args.width)
            base.load_field([(0,0), (100,0), (100,60), (0,60)])
            base.generate_work_lines()
            planner = DynamicObstacleplanner(base)
            planner.plan((10,5), (90,55), [(50,30,8)])
            planner.visualize_comparison('output/test_dynamic.png')
            print("Done: output/test_dynamic.png")
        elif args.test == 'smooth':
            from modules.path_smoothing import BSplineSmoother
            path = [(10, y) if i%2==0 else (90, y) for i, y in enumerate(range(5, 56, 10))]
            smoother = BSplineSmoother()
            smoothed, curvatures, headings = smoother.smooth(path)
            smoother.visualize(path, smoothed, curvatures, headings, 'output/test_smooth.png')
            print("Done: output/test_smooth.png")
        elif args.test == 'multi':
            from modules.multi_robot import MultiRobotPlanner
            multi = MultiRobotPlanner([(0,0), (120,0), (120,80), (0,80)], num_robots=3)
            multi.assign_work_lines()
            multi.plan_paths()
            multi.visualize('output/test_multi.png')
            print("Done: output/test_multi.png")
    
    elif args.full:
        run_full_pipeline(working_width=args.width, field_type=args.field)
    
    elif args.web:
        run_web_server(port=args.port)
    
    else:
        print("""
农机自动驾驶路径规划系统
=====================
用法:
  python main.py --full              # 运行完整流程
  python main.py --web              # 启动Web服务
  python main.py --test <module>    # 测试单个模块

模块: base, dynamic, smooth, multi
田块: rectangle, l_shape, irregular
示例: python main.py --full --field l_shape
      python main.py --web --port 8080
""")
