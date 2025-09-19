import asyncio
from bleak import BleakScanner
import struct
import time
from datetime import datetime

class BLEPacketCapture:
    def __init__(self):
        self.captured_packets = []
        
    def parse_advertisement_data(self, device, advertisement_data):
        """解析广播数据并转换为hcitool格式"""
        packet_info = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'address': device.address,
            'name': device.name or 'Unknown',
            'rssi': advertisement_data.rssi,
            'raw_data': [],
            'hci_cmd': ''
        }
        
        # 构建AD结构数据
        ad_data = []
        
        # 1. Flags (如果有RSSI说明是可发现的)
        ad_data.extend([0x02, 0x01, 0x06])  # Length=2, Type=Flags, Data=0x06
        
        # 2. Local Name
        if device.name:
            name_bytes = device.name.encode('utf-8')[:29]  # 限制长度
            if len(name_bytes) > 0:
                ad_data.append(len(name_bytes) + 1)
                ad_data.append(0x09)  # Complete Local Name
                ad_data.extend(name_bytes)
        
        # 3. Service UUIDs
        if advertisement_data.service_uuids:
            for uuid_str in advertisement_data.service_uuids:
                try:
                    # 处理16位UUID
                    if len(uuid_str) == 36:  # 完整UUID格式
                        uuid_16bit = int(uuid_str.split('-')[0], 16) & 0xFFFF
                        ad_data.extend([0x03, 0x03])  # Length=3, Type=Complete 16-bit UUIDs
                        ad_data.extend(struct.pack('<H', uuid_16bit))
                    else:
                        # 短UUID
                        uuid_val = int(uuid_str, 16) & 0xFFFF
                        ad_data.extend([0x03, 0x03])
                        ad_data.extend(struct.pack('<H', uuid_val))
                except:
                    pass
        
        # 4. Service Data
        if hasattr(advertisement_data, 'service_data') and advertisement_data.service_data:
            for uuid_str, data in advertisement_data.service_data.items():
                try:
                    uuid_16bit = int(uuid_str.split('-')[0], 16) & 0xFFFF
                    service_data_len = 2 + len(data) + 1
                    if service_data_len <= 31:
                        ad_data.append(service_data_len)
                        ad_data.append(0x16)  # Service Data 16-bit UUID
                        ad_data.extend(struct.pack('<H', uuid_16bit))
                        ad_data.extend(data)
                except:
                    pass
        
        # 5. Manufacturer Data
        if hasattr(advertisement_data, 'manufacturer_data') and advertisement_data.manufacturer_data:
            for company_id, data in advertisement_data.manufacturer_data.items():
                manu_data_len = 2 + len(data) + 1
                if manu_data_len <= 31:
                    ad_data.append(manu_data_len)
                    ad_data.append(0xFF)  # Manufacturer Specific Data
                    ad_data.extend(struct.pack('<H', company_id))
                    ad_data.extend(data)
        
        # 限制总长度不超过31字节
        if len(ad_data) > 31:
            ad_data = ad_data[:31]
        
        # 生成hcitool命令
        if ad_data:
            data_length = len(ad_data)
            # 补齐到31字节（用0填充）
            ad_data_padded = ad_data + [0x00] * (31 - len(ad_data))
            
            hci_params = [f'{data_length:02X}'] + [f'{b:02X}' for b in ad_data_padded]
            hci_cmd = f"sudo hcitool -i hci0 cmd 0x08 0x0008 {' '.join(hci_params)}"
            
            packet_info['raw_data'] = ad_data
            packet_info['hci_cmd'] = hci_cmd
        
        return packet_info
    
    async def scan_and_capture(self, duration=30, target_names=None, target_addresses=None):
        """扫描并捕获BLE广播包"""
        print(f"开始扫描BLE设备，持续{duration}秒...")
        print("=" * 80)
        
        def detection_callback(device, advertisement_data):
            # 过滤条件
            if target_names and device.name not in target_names:
                return
            if target_addresses and device.address not in target_addresses:
                return
            
            packet = self.parse_advertisement_data(device, advertisement_data)
            
            # 避免重复记录相同设备
            existing = next((p for p in self.captured_packets 
                           if p['address'] == packet['address'] and p["raw_data"] == packet["raw_data"]), None)
            
            if existing:
                # 更新时间戳和RSSI
                existing['timestamp'] = packet['timestamp']
                existing['rssi'] = packet['rssi']
            else:
                self.captured_packets.append(packet)
                self.print_packet_info(packet)
        
        # 开始扫描
        async with BleakScanner(detection_callback) as scanner:
            await asyncio.sleep(duration)
        
        print("\n扫描完成!")
        return self.captured_packets
    
    def print_packet_info(self, packet):
        """打印包信息"""
        print(f"时间: {packet['timestamp']}")
        print(f"地址: {packet['address']}")
        print(f"名称: {packet['name']}")
        print(f"RSSI: {packet['rssi']} dBm")
        if packet['raw_data']:
            print(f"原始数据: {' '.join(f'{b:02X}' for b in packet['raw_data'])}")
            print(f"HCI命令: {packet['hci_cmd']}")
        print("-" * 80)
    
    def save_to_file(self, filename="captured_ble_packets.txt"):
        """保存到文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("BLE广播包捕获结果\n")
            f.write("=" * 80 + "\n\n")
            
            for i, packet in enumerate(self.captured_packets, 1):
                f.write(f"包 #{i}\n")
                f.write(f"时间: {packet['timestamp']}\n")
                f.write(f"地址: {packet['address']}\n")
                f.write(f"名称: {packet['name']}\n")
                f.write(f"RSSI: {packet['rssi']} dBm\n")
                
                if packet['raw_data']:
                    f.write(f"原始数据: {' '.join(f'{b:02X}' for b in packet['raw_data'])}\n")
                    f.write(f"HCI命令:\n{packet['hci_cmd']}\n")
                f.write("\n" + "-" * 80 + "\n\n")
        
        print(f"结果已保存到: {filename}")
    
    def get_hci_commands(self):
        """获取所有HCI命令列表"""
        commands = []
        for packet in self.captured_packets:
            if packet['hci_cmd']:
                commands.append({
                    'name': packet['name'],
                    'address': packet['address'],
                    'command': packet['hci_cmd']
                })
        return commands
    
    def replay_packet(self, index):
        """重放指定的包"""
        if 0 <= index < len(self.captured_packets):
            packet = self.captured_packets[index]
            if packet['hci_cmd']:
                print(f"重放包 #{index + 1}: {packet['name']} ({packet['address']})")
                print(f"执行命令: {packet['hci_cmd']}")
                
                # 这里可以直接执行命令
                import subprocess
                cmd = packet['hci_cmd'].split()
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print("✓ 命令执行成功")
                    else:
                        print(f"✗ 命令执行失败: {result.stderr}")
                except Exception as e:
                    print(f"✗ 执行错误: {e}")
            else:
                print("该包没有有效的HCI命令")
        else:
            print("无效的包索引")

# 使用示例
async def main():
    capture = BLEPacketCapture()
    
    # 方式1: 扫描所有设备
    print("=== 扫描所有BLE设备 ===")
    await capture.scan_and_capture(duration=180)
    
    # 方式2: 只捕获特定名称的设备
    # await capture.scan_and_capture(
    #     duration=15, 
    #     target_names=["iPhone", "AirPods", "Mi Band"]
    # )
    
    # 方式3: 只捕获特定地址的设备
    # await capture.scan_and_capture(
    #     duration=120, 
    #     target_addresses=["AA:BB:CC:DD:EE:FF"]
    # )
    
    # 保存结果
    capture.save_to_file("ble_capture.txt")
    
    # 显示所有HCI命令
    print("\n=== 捕获的HCI命令 ===")
    commands = capture.get_hci_commands()
    for i, cmd in enumerate(commands):
        print(f"{i+1}. {cmd['name']} ({cmd['address']})")
        print(f"   {cmd['command']}")
        print()
    
    # 交互式重放
    if commands:
        while True:
            try:
                choice = input(f"选择要重放的包 (1-{len(commands)}, 或输入 'q' 退出): ")
                if choice.lower() == 'q':
                    break
                index = int(choice) - 1
                capture.replay_packet(index)
                print()
            except (ValueError, KeyboardInterrupt):
                break

if __name__ == "__main__":
    asyncio.run(main())
