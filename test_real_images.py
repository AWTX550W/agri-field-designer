"""Test fruit maturity detector on real images"""
import cv2
from fruit_maturity_detector import FruitMaturityDetector

detector = FruitMaturityDetector()

# Test images with real fruit photos
images = [
    r'C:\Users\Lenovo\WorkBuddy\automation-claw-20260409213706\test_images\tomato1.jpg',
    r'C:\Users\Lenovo\WorkBuddy\automation-claw-20260409213706\test_images\tomato2.jpg',
    r'C:\Users\Lenovo\WorkBuddy\automation-claw-20260409213706\test_images\apple_red.jpg',
]

print("🌾 田间数据采集测试 - 真实图片检测")
print("=" * 50)

for img_path in images:
    fname = img_path.split('\\')[-1]
    
    # detect() takes a file path, returns (result, visualized_output)
    result, visualized = detector.detect(img_path)
    
    if result is None:
        print(f"❌ {fname}: 加载失败")
        continue
    
    # Check if fruit detected (by looking at red_ratio)
    red_ratio_str = result.get("红色占比", "N/A")
    if red_ratio_str != "N/A" and red_ratio_str != "0.0%":
        fruit_detected = True
        status_icon = "🍅"
    else:
        fruit_detected = False
        status_icon = "❌"
    
    print(f"{status_icon} {fname}:")
    print(f"   {result.get('成熟度', '未知')}")
    print(f"   红色占比: {red_ratio_str}")
    print(f"   图像尺寸: {result.get('图像尺寸', 'N/A')}")
    print()
    
    # Save visualized output
    output_path = img_path.replace('.jpg', '_result.jpg')
    cv2.imwrite(output_path, visualized)
    print(f"   📊 可视化结果已保存: {output_path.split(chr(92))[-1]}")
