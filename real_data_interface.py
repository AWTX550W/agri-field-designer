# -*- coding: utf-8 -*-
"""
真实数据接口模块 - 农业机器人数据接入层
统一管理GPS、摄像头、传感器等外部数据源
"""

import cv2
import json
import time
import numpy as np
import sys
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# 修复Windows控制台UTF-8编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# ============ 数据结构定义 ============

@dataclass
class GPSPosition:
    """GPS坐标"""
    latitude: float   # 纬度
    longitude: float  # 经度
    altitude: float   # 海拔高度 (m)
    timestamp: str    # 时间戳

    def to_dict(self):
        return asdict(self)

@dataclass
class CameraFrame:
    """摄像头帧数据"""
    frame: np.ndarray     # 图像矩阵
    timestamp: str        # 时间戳
    camera_id: str        # 摄像头ID
    gps: Optional[GPSPosition] = None  # 关联的GPS位置

@dataclass
class SensorReading:
    """传感器读数"""
    sensor_type: str      # 传感器类型 (soil_moisture, temperature, etc.)
    value: float          # 数值
    unit: str             # 单位
    position: GPSPosition # 测量位置
    timestamp: str

# ============ 数据源基类 ============

class DataSource:
    """数据源抽象基类"""

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.is_active = False

    def start(self):
        """启动数据源"""
        self.is_active = True

    def stop(self):
        """停止数据源"""
        self.is_active = False

    def read(self) -> Any:
        """读取数据（子类实现）"""
        raise NotImplementedError

# ============ GPS数据源 ============

class GPSDataSource(DataSource):
    """GPS数据源 - 支持模拟/文件/串口"""

    def __init__(self, source_id: str, mode: str = "simulated", **kwargs):
        """
        :param mode: 模式 - 'simulated' | 'file' | 'serial'
        :param kwargs: 模式特定参数
          - simulated: initial_lat, initial_lon, speed (m/s)
          - file: file_path (JSON/CSV)
          - serial: port, baudrate
        """
        super().__init__(source_id)
        self.mode = mode
        self.kwargs = kwargs
        self.current_pos = None
        self.file_handle = None

        if mode == "simulated":
            self.lat = kwargs.get("initial_lat", 32.0617)  # 默认江苏大学附近
            self.lon = kwargs.get("initial_lon", 118.7772)
            self.speed = kwargs.get("speed", 1.0)  # m/s
            self.heading = 0  # 朝向角度

        elif mode == "file":
            self.file_path = Path(kwargs["file_path"])
            self.file_handle = open(self.file_path, 'r', encoding='utf-8')

        elif mode == "serial":
            # 这里可以集成pyserial读取真实GPS模块
            pass

    def read(self) -> GPSPosition:
        """读取GPS坐标"""
        if self.mode == "simulated":
            # 模拟移动（直线前进）
            from math import cos, sin, radians
            self.lat += (self.speed * cos(radians(self.heading)) / 111111)  # 纬度1度≈111111m
            self.lon += (self.speed * sin(radians(self.heading)) / (111111 * cos(radians(self.lat))))
            self.current_pos = GPSPosition(
                latitude=self.lat,
                longitude=self.lon,
                altitude=10.0,
                timestamp=datetime.now().isoformat()
            )

        elif self.mode == "file":
            # 从文件读取下一行（JSON格式）
            line = self.file_handle.readline()
            if line:
                data = json.loads(line.strip())
                self.current_pos = GPSPosition(**data)
            else:
                self.file_handle.seek(0)  # 循环读取
                line = self.file_handle.readline()
                data = json.loads(line.strip())
                self.current_pos = GPSPosition(**data)

        return self.current_pos

    def stop(self):
        super().stop()
        if self.file_handle:
            self.file_handle.close()

# ============ 摄像头数据源 ============

class CameraDataSource(DataSource):
    """摄像头数据源 - 支持摄像头/视频文件/图片文件夹"""

    def __init__(self, source_id: str, mode: str = "camera", **kwargs):
        """
        :param mode: 'camera' | 'video' | 'image_folder'
        :param kwargs: 模式特定参数
          - camera: device_id (默认0)
          - video: file_path
          - image_folder: folder_path
        """
        super().__init__(source_id)
        self.mode = mode
        self.cap = None
        self.image_files = []
        self.current_idx = 0

        if mode == "camera":
            self.device_id = kwargs.get("device_id", 0)
            self.cap = cv2.VideoCapture(self.device_id)

        elif mode == "video":
            self.video_path = Path(kwargs["file_path"])
            self.cap = cv2.VideoCapture(str(self.video_path))

        elif mode == "image_folder":
            self.folder_path = Path(kwargs["folder_path"])
            self.image_files = list(self.folder_path.glob("*.jpg")) + \
                             list(self.folder_path.glob("*.png"))
            self.image_files.sort()

    def start(self):
        self.is_active = True

    def read(self) -> Optional[CameraFrame]:
        """读取一帧图像"""
        if self.mode in ("camera", "video"):
            ret, frame = self.cap.read()
            if not ret:
                return None
            return CameraFrame(
                frame=frame,
                timestamp=datetime.now().isoformat(),
                camera_id=self.source_id
            )

        elif self.mode == "image_folder":
            if not self.image_files:
                return None
            if self.current_idx >= len(self.image_files):
                self.current_idx = 0  # 循环
            img_path = self.image_files[self.current_idx]
            frame = cv2.imread(str(img_path))
            self.current_idx += 1
            if frame is None:
                return None
            return CameraFrame(
                frame=frame,
                timestamp=datetime.now().isoformat(),
                camera_id=self.source_id
            )

    def stop(self):
        self.is_active = False
        if self.cap:
            self.cap.release()

# ============ 传感器数据源 ============

class SensorDataSource(DataSource):
    """传感器数据源 - 土壤湿度、温度等"""

    def __init__(self, source_id: str, sensor_type: str, mode: str = "simulated", **kwargs):
        """
        :param sensor_type: 'soil_moisture' | 'temperature' | 'npk' | 'lidar'
        :param mode: 'simulated' | 'file' | 'mqtt' | 'modbus'
        """
        super().__init__(source_id)
        self.sensor_type = sensor_type
        self.mode = mode
        self.kwargs = kwargs

        # 模拟参数
        if mode == "simulated":
            self.base_value = kwargs.get("base_value", 50.0)
            self.noise = kwargs.get("noise", 2.0)

    def read(self) -> SensorReading:
        """读取传感器数据"""
        position = GPSPosition(
            latitude=0, longitude=0, altitude=0,
            timestamp=datetime.now().isoformat()
        )

        if self.mode == "simulated":
            import random
            value = self.base_value + random.uniform(-self.noise, self.noise)

            # 根据传感器类型设置单位
            units = {
                "soil_moisture": "%",
                "temperature": "°C",
                "npk": "mg/kg",
                "lidar": "m"
            }
            unit = units.get(self.sensor_type, "")

            return SensorReading(
                sensor_type=self.sensor_type,
                value=round(value, 2),
                unit=unit,
                position=position,
                timestamp=datetime.now().isoformat()
            )

        return None

# ============ 数据融合器 ============

class DataFuser:
    """多源数据融合 - 将GPS与摄像头帧对齐"""

    def __init__(self):
        self.sources: Dict[str, DataSource] = {}

    def register_source(self, name: str, source: DataSource):
        """注册数据源"""
        self.sources[name] = source

    def get_synced_data(self) -> Dict[str, Any]:
        """获取同步数据（所有源的最新数据）"""
        synced = {
            "timestamp": datetime.now().isoformat(),
            "sources": {}
        }

        for name, source in self.sources.items():
            if source.is_active:
                try:
                    data = source.read()
                    if data:
                        synced["sources"][name] = data
                except Exception as e:
                    print(f"[警告] 数据源 {name} 读取失败: {e}")

        return synced

# ============ 便捷函数 ============

def create_gps_trace_file(output_path: str, num_points: int = 100):
    """生成GPS轨迹文件（测试用）"""
    import random
    trace = []
    lat, lon = 32.0617, 118.7772  # 江苏大学
    for i in range(num_points):
        lat += random.uniform(-0.001, 0.001)
        lon += random.uniform(-0.001, 0.001)
        trace.append(GPSPosition(
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            altitude=10.0,
            timestamp=datetime.now().isoformat()
        ).to_dict())
    with open(output_path, 'w', encoding='utf-8') as f:
        for point in trace:
            f.write(json.dumps(point, ensure_ascii=False) + '\n')
    print(f"✅ GPS轨迹文件已生成: {output_path} ({num_points}个点)")

# ============ 示例用法 ============

if __name__ == "__main__":
    print("📍 真实数据接口模块演示\n")

    # 1. GPS模拟器
    gps = GPSDataSource("gps1", mode="simulated", initial_lat=32.0617, initial_lon=118.7772, speed=1.0)
    gps.start()
    print("GPS位置:", gps.read().to_dict())
    gps.stop()

    # 2. 生成GPS轨迹文件
    create_gps_trace_file("gps_trace.json", num_points=10)

    # 3. 摄像头模拟（从文件夹读取）
    print("\n📷 摄像头接口测试:")
    cam = CameraDataSource("cam1", mode="image_folder", folder_path=".")
    cam.start()
    frame = cam.read()
    if frame:
        print(f"   帧尺寸: {frame.frame.shape}")
        print(f"   时间戳: {frame.timestamp}")
    cam.stop()

    # 4. 传感器模拟
    print("\n🌡️  传感器接口测试:")
    sensor = SensorDataSource("soil1", "soil_moisture", mode="simulated", base_value=65, noise=3)
    reading = sensor.read()
    print(f"   土壤湿度: {reading.value}{reading.unit}")

    print("\n✅ 所有接口测试完成，可在项目中导入使用")
