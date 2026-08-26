"""
二进制序列化/反序列化模块
支持网格的高效二进制存储和加载
"""

import struct
import logging
from typing import Dict, Tuple
from grid_3d import Grid3D

logger = logging.getLogger(__name__)

# 二进制格式版本
BINARY_FORMAT_VERSION = 1


class BinarySerializer:
    """3D网格二进制序列化器"""
    
    @staticmethod
    def serialize(grid: Grid3D) -> bytes:
        """
        将网格序列化为二进制格式
        
        格式:
        - Header (4 bytes): 版本号
        - Resolution (4 bytes): 网格分辨率
        - Nodes Count (4 bytes): 节点数量
        - Nodes Data: 每个节点 (12 bytes) = 3个4字节整数
        - Elements Count (4 bytes): 单元数量
        - Elements Data: 每个单元 (48 bytes) = 8个节点ID + 3个索引 + 1个层级
        - Adjacency Count (4 bytes): 邻接关系数量
        - Adjacency Data: 每个邻接 (28 bytes) = ID + 6个邻接ID
        
        Returns:
            二进制数据
        """
        data = bytearray()
        
        # Header
        data.extend(struct.pack('I', BINARY_FORMAT_VERSION))
        data.extend(struct.pack('I', grid.resolution))
        
        # Nodes
        data.extend(struct.pack('I', len(grid.nodes)))
        for node_id in sorted(grid.nodes.keys()):
            x, y, z = grid.nodes[node_id]
            data.extend(struct.pack('III', x, y, z))
        
        # Elements
        data.extend(struct.pack('I', len(grid.elements)))
        for elem_id in sorted(grid.elements.keys()):
            elem = grid.elements[elem_id]
            data.extend(struct.pack('I', elem_id))
            # 8个节点
            for node_id in elem["nodes"]:
                data.extend(struct.pack('I', node_id))
            # 3个索引
            for idx in elem["indices"]:
                data.extend(struct.pack('I', idx))
            # 层级
            data.extend(struct.pack('I', elem.get("level", 0)))
        
        # Adjacency
        data.extend(struct.pack('I', len(grid.adjacency)))
        for elem_id in sorted(grid.adjacency.keys()):
            neighbors = grid.adjacency[elem_id]
            data.extend(struct.pack('I', elem_id))
            data.extend(struct.pack('IIIIII', 
                neighbors["left"], neighbors["right"],
                neighbors["front"], neighbors["back"],
                neighbors["bottom"], neighbors["top"]
            ))
        
        logger.info(f"Serialized grid: {len(data)} bytes")
        return bytes(data)
    
    @staticmethod
    def deserialize(data: bytes) -> Grid3D:
        """
        从二进制数据反序列化网格
        
        Args:
            data: 二进制数据
            
        Returns:
            Grid3D 对象
        """
        offset = 0
        
        # Header
        version = struct.unpack_from('I', data, offset)[0]
        offset += 4
        if version != BINARY_FORMAT_VERSION:
            raise ValueError(f"Unsupported binary format version: {version}")
        
        resolution = struct.unpack_from('I', data, offset)[0]
        offset += 4
        
        # 创建空网格
        grid = Grid3D.__new__(Grid3D)
        grid.resolution = resolution
        grid.elements = {}
        grid.nodes = {}
        grid.adjacency = {}
        
        # Nodes
        node_count = struct.unpack_from('I', data, offset)[0]
        offset += 4
        for _ in range(node_count):
            x, y, z = struct.unpack_from('III', data, offset)
            offset += 12
            node_id = len(grid.nodes) + 1
            grid.nodes[node_id] = (x, y, z)
        
        # Elements
        elem_count = struct.unpack_from('I', data, offset)[0]
        offset += 4
        for _ in range(elem_count):
            elem_id = struct.unpack_from('I', data, offset)[0]
            offset += 4
            
            nodes = []
            for _ in range(8):
                node_id = struct.unpack_from('I', data, offset)[0]
                offset += 4
                nodes.append(node_id)
            
            indices = []
            for _ in range(3):
                idx = struct.unpack_from('I', data, offset)[0]
                offset += 4
                indices.append(idx)
            
            level = struct.unpack_from('I', data, offset)[0]
            offset += 4
            
            grid.elements[elem_id] = {
                "indices": tuple(indices),
                "nodes": nodes,
                "level": level
            }
        
        # Adjacency
        adj_count = struct.unpack_from('I', data, offset)[0]
        offset += 4
        for _ in range(adj_count):
            elem_id = struct.unpack_from('I', data, offset)[0]
            offset += 4
            left, right, front, back, bottom, top = struct.unpack_from('IIIIII', data, offset)
            offset += 24
            
            grid.adjacency[elem_id] = {
                "left": left,
                "right": right,
                "front": front,
                "back": back,
                "bottom": bottom,
                "top": top
            }
        
        logger.info(f"Deserialized grid: {len(grid.elements)} elements, {len(grid.nodes)} nodes")
        return grid
    
    @staticmethod
    def save_to_file(grid: Grid3D, filename: str):
        """保存网格到二进制文件"""
        data = BinarySerializer.serialize(grid)
        with open(filename, 'wb') as f:
            f.write(data)
        logger.info(f"Grid saved to {filename}")
    
    @staticmethod
    def load_from_file(filename: str) -> Grid3D:
        """从二进制文件加载网格"""
        with open(filename, 'rb') as f:
            data = f.read()
        logger.info(f"Grid loaded from {filename}")
        return BinarySerializer.deserialize(data)
