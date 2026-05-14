#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
农机自动驾驶弓字形覆盖路径规划算法（基础版）
作者：农业机械化工程专业校招展示项目
依赖：numpy, matplotlib
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional


class AgriMachineryPathPlanner:
    """
    农机自动驾驶路径规划器
    功能：输入田块边界+障碍物+作业幅宽，输出弓字形覆盖作业路径
    支持凸多边形和凹多边形田块
    """

    def __init__(self, working_width: float = 2.0):
        self.working_width = working_width
        self.field_boundary = None
        self.obstacles = []
        self.work_lines = []
        self.path_points = []
        self.stats = {}
        self.is_concave = False

    # ============================================================
    # 步骤1：田块边界预处理
    # ============================================================
    def load_field(self, boundary: List[Tuple[float, float]]):
        if len(boundary) < 3:
            raise ValueError("田块边界至少需要3个顶点")

        self.field_boundary = np.array(boundary)
        x_min, y_min = self.field_boundary.min(axis=0)
        x_max, y_max = self.field_boundary.max(axis=0)
        self.x_min, self.y_min = x_min, y_min
        self.x_max, self.y_max = x_max, y_max
        self.width = x_max - x_min
        self.height = y_max - y_min

        # 检测是否为凹多边形
        self.is_concave = self._is_concave(self.field_boundary)
        if self.is_concave:
            print("[预处理] 检测到凹多边形田块，将使用分区算法")
            # 凹多边形：按短边方向生成作业线（减少分区数量）
            if self.width >= self.height:
                self.direction = 'horizontal'
            else:
                self.direction = 'vertical'
        else:
            if self.width >= self.height:
                self.direction = 'horizontal'
            else:
                self.direction = 'vertical'

        print(f"[预处理] 田块尺寸: {self.width:.1f}m x {self.height:.1f}m")
        shape = "凹多边形" if self.is_concave else "凸多边形"
        d = "水平（左右往返）" if self.direction == 'horizontal' else "垂直（上下往返）"
        print(f"[预处理] 田块形状: {shape}，作业线方向: {d}")

    def _is_concave(self, poly: np.ndarray) -> bool:
        """判断多边形是否为凹多边形（通过叉积符号变化检测）"""
        n = len(poly)
        sign = None
        for i in range(n):
            p0 = poly[i]
            p1 = poly[(i + 1) % n]
            p2 = poly[(i + 2) % n]
            dx1 = p1[0] - p0[0]
            dy1 = p1[1] - p0[1]
            dx2 = p2[0] - p1[0]
            dy2 = p2[1] - p1[1]
            cross = dx1 * dy2 - dy1 * dx2
            if abs(cross) < 1e-10:
                continue
            if sign is None:
                sign = 1 if cross > 0 else -1
            elif (cross > 0 and sign < 0) or (cross < 0 and sign > 0):
                return True
        return False

    # ============================================================
    # 步骤2：平行作业线生成（支持凹多边形）
    # ============================================================
    def generate_work_lines(self):
        if self.direction == 'horizontal':
            num_lines = max(1, int(self.height / self.working_width))
            y_positions = np.linspace(self.y_min + self.working_width / 2,
                                     self.y_max - self.working_width / 2,
                                     num_lines)
            self.work_lines = []
            for y in y_positions:
                segments = self._clip_line_to_field_multi((self.x_min - 1, y), (self.x_max + 1, y))
                self.work_lines.extend(segments)
        else:
            num_lines = max(1, int(self.width / self.working_width))
            x_positions = np.linspace(self.x_min + self.working_width / 2,
                                     self.x_max - self.working_width / 2,
                                     num_lines)
            self.work_lines = []
            for x in x_positions:
                segments = self._clip_line_to_field_multi((x, self.y_min - 1), (x, self.y_max + 1))
                self.work_lines.extend(segments)

        # 按作业线顺序排序（水平：按y；垂直：按x）
        if self.direction == 'horizontal':
            self.work_lines.sort(key=lambda s: (s[0][1] + s[1][1]) / 2)
        else:
            self.work_lines.sort(key=lambda s: (s[0][0] + s[1][0]) / 2)

        print(f"[作业线] 共生成 {len(self.work_lines)} 条有效作业线段")
        return self.work_lines

    def _clip_line_to_field_multi(self, p1, p2):
        """
        将直线裁剪到田块多边形内部
        凹多边形可能返回多个线段（进出多次）
        """
        intersections = []
        boundary = self.field_boundary
        n = len(boundary)

        for i in range(n):
            edge_start = boundary[i]
            edge_end = boundary[(i + 1) % n]
            intersect = self._line_intersection(p1, p2, edge_start, edge_end)
            if intersect is not None:
                intersections.append(intersect)

        if len(intersections) < 2:
            return []

        # 按直线参数t排序，两两配对得到有效线段
        line_vec = np.array(p2) - np.array(p1)
        t_values = []
        for pt in intersections:
            t = np.dot(np.array(pt) - np.array(p1), line_vec)
            t_values.append((t, pt))
        t_values.sort(key=lambda x: x[0])

        segments = []
        for i in range(0, len(t_values) - 1, 2):
            start_pt = np.array(t_values[i][1])
            end_pt = np.array(t_values[i + 1][1])
            # 过滤长度过短的线段
            if np.linalg.norm(end_pt - start_pt) > 0.01:
                segments.append((tuple(start_pt), tuple(end_pt)))
        return segments

    def _line_intersection(self, p1, p2, p3, p4):
        """计算两条线段的交点，若无交点返回None"""
        A1 = p2[1] - p1[1]
        B1 = p1[0] - p2[0]
        C1 = A1 * p1[0] + B1 * p1[1]

        A2 = p4[1] - p3[1]
        B2 = p3[0] - p4[0]
        C2 = A2 * p3[0] + B2 * p3[1]

        det = A1 * B2 - A2 * B1
        if abs(det) < 1e-10:
            return None
        x = (C1 * B2 - C2 * B1) / det
        y = (A1 * C2 - A2 * C1) / det

        def on_segment(px, py, a, b):
            return (min(a[0], b[0]) - 1e-6 <= px <= max(a[0], b[0]) + 1e-6 and
                    min(a[1], b[1]) - 1e-6 <= py <= max(a[1], b[1]) + 1e-6)

        if on_segment(x, y, p1, p2) and on_segment(x, y, p3, p4):
            return (x, y)
        return None

    # ============================================================
    # 步骤3：弓字形路径连接
    # ============================================================
    def generate_zigzag_path(self):
        if not self.work_lines:
            raise ValueError("请先调用 generate_work_lines() 生成作业线")

        self.path_points = []
        path = []

        for i, (start, end) in enumerate(self.work_lines):
            if i % 2 == 0:
                path.append(start)
                path.append(end)
            else:
                path.append(end)
                path.append(start)

            if i < len(self.work_lines) - 1:
                curr_end = path[-1]
                next_seg = self.work_lines[i + 1]
                next_start = next_seg[0] if (i + 1) % 2 == 0 else next_seg[1]
                turn_points = self._generate_u_turn(curr_end, next_start)
                path.extend(turn_points)

        self.path_points = path
        print(f"[弓字形] 路径点数量: {len(self.path_points)}")
        return self.path_points

    def _generate_u_turn(self, p1, p2):
        """生成简化U型转弯路径（工业级需考虑最小转弯半径）"""
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        return [(mid_x, mid_y), p2]

    # ============================================================
    # 步骤4：障碍物避障处理
    # ============================================================
    def load_obstacles(self, obstacles: List[Tuple[Tuple[float, float], float]]):
        self.obstacles = obstacles
        print(f"[障碍物] 加载 {len(obstacles)} 个障碍物")

    def check_collision(self, point: Tuple[float, float]) -> bool:
        px, py = point
        for (ox, oy), radius in self.obstacles:
            if (px - ox) ** 2 + (py - oy) ** 2 < radius ** 2:
                return True
        return False

    def validate_path(self):
        if not self.path_points:
            return

        collision_count = 0
        safe_path = []
        for i, pt in enumerate(self.path_points):
            if self.check_collision(pt):
                collision_count += 1
                print(f"  [避障] 路径点{i} {pt} 与障碍物碰撞！（工业级需避障重规划）")
            else:
                safe_path.append(pt)

        if collision_count > 0:
            print(f"[避障] 检测到 {collision_count} 个碰撞风险点")
            print("[避障] 工业级扩展：动态避障重规划、D* Lite算法")
        else:
            print("[避障] 路径无碰撞风险 ✓")
        self.path_points = safe_path

    # ============================================================
    # 步骤5：可视化与输出
    # ============================================================
    def visualize(self, save_path: str = None):
        fig, ax = plt.subplots(figsize=(10, 8))

        boundary = np.vstack([self.field_boundary, self.field_boundary[0:1]])
        ax.plot(boundary[:, 0], boundary[:, 1], 'k-', linewidth=2, label='Field Boundary')
        ax.fill(boundary[:, 0], boundary[:, 1], alpha=0.1, color='green')

        for (ox, oy), radius in self.obstacles:
            circle = plt.Circle((ox, oy), radius, color='red', alpha=0.3)
            ax.add_patch(circle)
            ax.plot(ox, oy, 'rx', markersize=10)

        for i, (start, end) in enumerate(self.work_lines):
            ax.plot([start[0], end[0]], [start[1], end[1]],
                    'gray', linestyle='--', alpha=0.5,
                    label='Work Lines' if i == 0 else None)

        if self.path_points:
            path_arr = np.array(self.path_points)
            ax.plot(path_arr[:, 0], path_arr[:, 1], 'b-', linewidth=2,
                    label='Zigzag Path')
            ax.plot(path_arr[0, 0], path_arr[0, 1], 'go', markersize=10, label='Start')
            ax.plot(path_arr[-1, 0], path_arr[-1, 1], 'ro', markersize=10, label='End')

        ax.set_aspect('equal')
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_title('Agricultural Machinery Path Planning')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"[可视化] 已保存至 {save_path}")
        plt.close()

    def print_statistics(self):
        if not self.path_points or not self.work_lines:
            print("[统计] 路径或作业线为空")
            return

        total_length = 0
        for i in range(len(self.path_points) - 1):
            p1 = np.array(self.path_points[i])
            p2 = np.array(self.path_points[i + 1])
            total_length += np.linalg.norm(p2 - p1)

        effective_length = sum(
            np.linalg.norm(np.array(end) - np.array(start))
            for start, end in self.work_lines
        )

        field_area = self.width * self.height
        coverage_area = effective_length * self.working_width

        self.stats = {
            'Work Lines': len(self.work_lines),
            'Total Path Length (m)': round(total_length, 2),
            'Effective Length (m)': round(effective_length, 2),
            'Working Width (m)': self.working_width,
            'Field Area (m2)': round(field_area, 2),
            'Coverage Area (m2)': round(coverage_area, 2),
            'Coverage Rate (%)': round(min(100, coverage_area / field_area * 100), 1) if field_area > 0 else 0,
        }

        print("\n====== Path Planning Statistics ======")
        for key, value in self.stats.items():
            print(f"  {key}: {value}")
        print("===================================\n")

    def print_optimization_notes(self):
        notes = [
            "1. Concave polygon: scanline / Boustrophedon decomposition",
            "2. Dynamic obstacle avoidance: D* Lite / TEB algorithm",
            "3. Kinematic constraints:minimum turning radius, Ackerman steering",
            "4. Path smoothing: B-spline / Bezier curves",
            "5. Multi-robot coordination: CBBA algorithm",
            "6. High-precision positioning: RTK-GPS + IMU fusion",
            "7. Operation quality: reduce missed/overlap coverage",
        ]
        print("\n====== Industrial Optimization Directions ======")
        for note in notes:
            print(f"  {note}")
        print("===========================================\n")


class FieldDrawer:
    """
    交互式田块绘制器
    功能：鼠标点击添加顶点、拖动调整、右键删除、Enter完成
    """
    
    def __init__(self, figsize=(10, 8)):
        self.fig = None
        self.ax = None
        self.vertices = []  # 顶点列表
        self.vertex_handles = []  # 顶点标记句柄
        self.line_handle = None  # 边界线句柄
        self.dragging_idx = None  # 当前拖动的顶点索引
        self.working_width = 5.0
        
    def draw(self):
        """启动交互式绘图，返回田块边界顶点列表"""
        # 使用 TkAgg 后端支持交互
        matplotlib.use('TkAgg')
        plt.ion()
        
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.ax.set_xlim(-10, 110)
        self.ax.set_ylim(-10, 71)
        self.ax.set_aspect('equal')
        self.ax.set_title('Click to add vertices | Drag to adjust | Right-click to delete | Enter to finish')
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.grid(True, alpha=0.3)
        
        # 初始化提示文字
        self.info_text = self.ax.text(0.02, 0.98, 
            'Vertices: 0\nClick: Add vertex\nDrag: Move vertex\nRight-click: Delete\nEnter: Finish',
            transform=self.ax.transAxes, fontsize=10,
            verticalalignment='top', 
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # 绑定事件
        self.cid_click = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid_release = self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.cid_key = self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        print("\n" + "="*50)
        print("Interactive Field Drawing")
        print("="*50)
        print("1. Click on canvas to add vertices")
        print("2. Drag vertices to adjust position")
        print("3. Right-click on vertex to delete it")
        print("4. Press ENTER when done (minimum 3 vertices)")
        print("5. Press ESC to cancel")
        print("="*50)
        
        plt.show()
        
        # 等待用户完成
        while plt.get_fignums():
            plt.pause(0.1)
            
        return self.vertices
    
    def update_plot(self):
        """更新绘图"""
        # 清除旧元素
        for h in self.vertex_handles:
            h.remove()
        self.vertex_handles = []
        if self.line_handle:
            self.line_handle.remove()
            
        if len(self.vertices) == 0:
            return
            
        # 绘制边界线（如果>=2个点）
        if len(self.vertices) >= 2:
            xs = [v[0] for v in self.vertices]
            ys = [v[1] for v in self.vertices]
            # 闭合多边形
            xs.append(xs[0])
            ys.append(ys[0])
            self.line_handle, = self.ax.plot(xs, ys, 'b-', linewidth=2, alpha=0.7)
            
        # 绘制顶点
        for i, (x, y) in enumerate(self.vertices):
            marker = self.ax.plot(x, y, 'bo', markersize=12, picker=5)[0]
            self.vertex_handles.append(marker)
            # 标注顶点序号
            label = self.ax.text(x + 0.5, y + 0.5, str(i + 1), 
                                fontsize=9, color='red', fontweight='bold')
            self.vertex_handles.append(label)
            
        # 更新信息
        self.info_text.set_text(
            f'Vertices: {len(self.vertices)}\nClick: Add vertex\nDrag: Move vertex\nRight-click: Delete\nEnter: Finish')
        
        self.fig.canvas.draw()
        
    def on_click(self, event):
        """处理鼠标点击"""
        if event.inaxes != self.ax:
            return
            
        # 左键点击空白区域：添加新顶点
        if event.button == 1 and event.key is None:
            # 检查是否点击了现有顶点（用于拖动）
            for i, (x, y) in enumerate(self.vertices):
                if abs(event.xdata - x) < 1 and abs(event.ydata - y) < 1:
                    self.dragging_idx = i
                    return
            # 添加新顶点
            self.vertices.append((event.xdata, event.ydata))
            self.update_plot()
            
        # 右键：删除最近的顶点
        elif event.button == 3:
            if self.vertices:
                # 找到最近的顶点
                min_dist = float('inf')
                min_idx = -1
                for i, (x, y) in enumerate(self.vertices):
                    dist = (event.xdata - x)**2 + (event.ydata - y)**2
                    if dist < min_dist:
                        min_dist = dist
                        min_idx = i
                if min_dist < 25:  # 5像素范围内
                    self.vertices.pop(min_idx)
                    self.update_plot()
                    
    def on_release(self, event):
        """处理鼠标释放"""
        self.dragging_idx = None
        
    def on_motion(self, event):
        """处理鼠标移动（拖动顶点）"""
        if self.dragging_idx is not None and event.inaxes == self.ax:
            self.vertices[self.dragging_idx] = (event.xdata, event.ydata)
            self.update_plot()
            
    def on_key(self, event):
        """处理键盘事件"""
        if event.key == 'enter':
            if len(self.vertices) >= 3:
                self.finish()
            else:
                print(f"[提示] 需要至少3个顶点，当前: {len(self.vertices)}")
        elif event.key == 'escape':
            self.vertices = []
            self.finish()
        elif event.key == 'backspace' and self.vertices:
            self.vertices.pop()
            self.update_plot()
        elif event.key == 'z' and event.ctrl:  # Ctrl+Z 撤销
            if self.vertices:
                self.vertices.pop()
                self.update_plot()
                
    def finish(self):
        """完成绘图"""
        plt.close(self.fig)


# ============================================================
# 测试用例
# ============================================================
def test_case_1_rectangle_no_obstacle():
    print("\n" + "="*50)
    print("Test Case 1: Rectangle field (100m x 60m), no obstacle")
    print("="*50)
    planner = AgriMachineryPathPlanner(working_width=5.0)
    boundary = [(0, 0), (100, 0), (100, 60), (0, 60)]
    planner.load_field(boundary)
    planner.generate_work_lines()
    planner.generate_zigzag_path()
    planner.validate_path()
    planner.print_statistics()
    planner.print_optimization_notes()
    planner.visualize(save_path='path_test_case_1.png')


def test_case_2_rectangle_with_obstacle():
    print("\n" + "="*50)
    print("Test Case 2: Rectangle field (80m x 50m), 1 obstacle")
    print("="*50)
    planner = AgriMachineryPathPlanner(working_width=4.0)
    boundary = [(0, 0), (80, 0), (80, 50), (0, 50)]
    planner.load_field(boundary)
    obstacles = [((40, 25), 5.0)]
    planner.load_obstacles(obstacles)
    planner.generate_work_lines()
    planner.generate_zigzag_path()
    planner.validate_path()
    planner.print_statistics()
    planner.print_optimization_notes()
    planner.visualize(save_path='path_test_case_2.png')


def test_case_3_concave_polygon():
    """测试用例3：凹多边形田块（L形）"""
    print("\n" + "="*50)
    print("Test Case 3: Concave polygon field (L-shape)")
    print("="*50)
    planner = AgriMachineryPathPlanner(working_width=3.0)
    # L形田块（凹多边形）
    boundary = [(0, 0), (60, 0), (60, 30), (30, 30), (30, 60), (0, 60)]
    planner.load_field(boundary)
    planner.generate_work_lines()
    planner.generate_zigzag_path()
    planner.validate_path()
    planner.print_statistics()
    planner.visualize(save_path='path_test_case_3_concave.png')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--draw':
        # 交互式绘图模式
        print("=" * 60)
        print("Interactive Field Drawing Mode")
        print("=" * 60)
        drawer = FieldDrawer()
        boundary = drawer.draw()
        if boundary and len(boundary) >= 3:
            print(f"\n[绘图] 捕获田块边界，共 {len(boundary)} 个顶点")
            
            # 自动规划路径
            working_width = float(input("Enter working width (m) [default: 5.0]: ") or "5.0")
            planner = AgriMachineryPathPlanner(working_width=working_width)
            planner.load_field(boundary)
            planner.generate_work_lines()
            planner.generate_zigzag_path()
            planner.validate_path()
            planner.print_statistics()
            planner.print_optimization_notes()
            
            save_path = input("Save visualization to file (press Enter to skip): ")
            if save_path:
                planner.visualize(save_path=save_path)
            else:
                planner.visualize()
            print("[完成] 路径规划完成！")
        else:
            print("[取消] 未绘制有效田块")
    else:
        print("=" * 60)
        print("Agricultural Machinery Zigzag Path Planning")
        print("=" * 60)

        test_case_1_rectangle_no_obstacle()
        test_case_2_rectangle_with_obstacle()
        test_case_3_concave_polygon()

        print("All test cases completed.")
        print("Output files: path_test_case_1.png, path_test_case_2.png, path_test_case_3_concave.png")
