# -*- coding: utf-8 -*-
"""
农业机器人果实成熟度检测 - AI视觉版
基于颜色特征判断番茄成熟度（红/青分类）
适合30分钟快速上手，跑通demo
"""

import cv2
import numpy as np
import sys
from pathlib import Path

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class FruitMaturityDetector:
    """果实成熟度检测器"""

    def __init__(self):
        # HSV颜色空间阈值（针对番茄红）
        self.lower_red = np.array([0, 100, 100])
        self.upper_red = np.array([10, 255, 255])
        self.lower_green = np.array([35, 50, 50])
        self.upper_green = np.array([85, 255, 255])

    def detect(self, image_path):
        """检测图像中果实的成熟度"""
        img = cv2.imread(image_path)
        if img is None:
            print(f"❌ 无法读取图像: {image_path}")
            return None

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 提取红色区域（成熟）和绿色区域（未成熟）
        red_mask = cv2.inRange(hsv, self.lower_red, self.upper_red)
        green_mask = cv2.inRange(hsv, self.lower_green, self.upper_green)

        red_pixels = cv2.countNonZero(red_mask)
        green_pixels = cv2.countNonZero(green_mask)
        total_fruit = red_pixels + green_pixels

        if total_fruit == 0:
            maturity = "未检测到果实"
            red_ratio = 0.0
        else:
            red_ratio = red_pixels / total_fruit
            if red_ratio > 0.6:
                maturity = "成熟 (可采摘)"
            elif red_ratio > 0.3:
                maturity = "半成熟 (继续生长)"
            else:
                maturity = "未成熟 (需等待)"

        result = {
            "成熟度": maturity,
            "红色占比": f"{red_ratio:.1%}" if total_fruit > 0 else "N/A",
            "图像尺寸": img.shape[:2]
        }

        # 生成可视化结果
        output = img.copy()
        output[red_mask > 0] = [0, 0, 255]  # 成熟区域标红
        output[green_mask > 0] = [0, 255, 0]  # 未成熟区域标绿

        return result, output

    def batch_detect(self, folder_path):
        """批量检测文件夹中的图像"""
        results = []
        folder = Path(folder_path)
        for img_file in folder.glob("*.jpg") + folder.glob("*.png"):
            result, _ = self.detect(str(img_file))
            if result:
                results.append({img_file.name: result})
        return results


# ============ 示例用法 ============

if __name__ == "__main__":
    detector = FruitMaturityDetector()

    # 示例1: 单张图像检测（替换为你的图片路径）
    # result, visualized = detector.detect("tomato.jpg")
    # if result:
    #     print("检测结果:", result)
    #     cv2.imwrite("result_tomato.jpg", visualized)

    # 示例2: 模拟数据（无图时展示逻辑）
    print("✅ 果实成熟度检测器已就绪")
    print("\n📌 使用步骤:")
    print("1. 准备一张番茄图片，命名为 'tomato.jpg'")
    print("2. 取消注释第67-70行代码")
    print("3. 运行: python fruit_maturity_detector.py")
    print("\n🎯 检测逻辑:")
    print("   - 红色像素 > 60% → 成熟 (可采摘)")
    print("   - 红色像素 30-60% → 半成熟")
    print("   - 红色像素 < 30% → 未成熟")

    # 示例3: 无人机路径规划（附加彩蛋）
    print("\n\n🚁 附加：简单无人机路径规划算法")
    print("""
def generate_lawn_mowing_path(area_width, area_height, step=2.0):
    '''生成草坪修剪路径（往返扫描）'''
    path = []
    direction = 1
    for y in np.arange(0, area_height, step):
        if direction == 1:
            path.extend([(x, y) for x in np.arange(0, area_width, step)])
        else:
            path.extend([(x, y) for x in np.arange(area_width, 0, -step)])
        direction *= -1
    return path
# 用法: path = generate_lawn_mowing_path(100, 80, step=2)
# 适合：农田巡查、播种、喷洒作业
""")
