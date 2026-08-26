"""
网格扩散和收缩模块
用于多分辨率网格生成和自适应加密/粗化
"""

from typing import Set, Dict, List, Tuple, Optional
import logging
from grid_3d import Grid3D

logger = logging.getLogger(__name__)


class GridExpander:
    """网格扩散器 - 细化网格"""
    
    @staticmethod
    def expand_element(grid: Grid3D, elem_id: int, subdivisions: int = 2) -> Set[int]:
        """
        扩散单个单元 - 将其细分为更小的单元
        
        Args:
            grid: 网格对象
            elem_id: 要细分的单元ID
            subdivisions: 细分次数 (2=8个子单元, 3=27个子单元)
            
        Returns:
            新生成的子单元ID集合
        """
        if elem_id not in grid.elements:
            logger.warning(f"Element {elem_id} not found")
            return set()
        
        elem = grid.elements[elem_id]
        i, j, k = elem["indices"]
        current_level = elem.get("level", 0)
        
        # 获取原单元的8个顶点坐标
        nodes = elem["nodes"]
        node_coords = [grid.nodes[nid] for nid in nodes]
        
        new_elem_ids = set()
        max_elem_id = max(grid.elements.keys()) if grid.elements else 0
        
        # 细分单元
        for di in range(subdivisions):
            for dj in range(subdivisions):
                for dk in range(subdivisions):
                    max_elem_id += 1
                    
                    # 计算子单元的8个顶点坐标
                    sub_nodes = []
                    for corner in range(8):
                        # 从原单元8个顶点中插值得到子单元顶点
                        x0, y0, z0 = node_coords[corner]
                        dx = 1.0 / subdivisions
                        
                        # 计算新顶点坐标
                        x = x0 + di * dx
                        y = y0 + dj * dx
                        z = z0 + dk * dx
                        
                        # 查找或创建节点
                        coord = (x, y, z)
                        if coord not in grid.nodes.values():
                            node_id = max(grid.nodes.keys()) + 1 if grid.nodes else 1
                            grid.nodes[node_id] = coord
                        else:
                            node_id = [nid for nid, c in grid.nodes.items() if c == coord][0]
                        
                        sub_nodes.append(node_id)
                    
                    # 创建子单元
                    grid.elements[max_elem_id] = {
                        "indices": (i + di/subdivisions, j + dj/subdivisions, k + dk/subdivisions),
                        "nodes": sub_nodes,
                        "level": current_level + 1,
                        "parent": elem_id
                    }
                    new_elem_ids.add(max_elem_id)
        
        # 标记原单元为已细分
        elem["subdivided"] = True
        elem["children"] = list(new_elem_ids)
        
        logger.info(f"Expanded element {elem_id} into {len(new_elem_ids)} sub-elements")
        return new_elem_ids
    
    @staticmethod
    def expand_region(grid: Grid3D, elem_ids: Set[int], subdivisions: int = 2) -> Set[int]:
        """
        扩散一个区域内的所有单元
        
        Args:
            grid: 网格对象
            elem_ids: 要扩散的单元ID集合
            subdivisions: 细分参数
            
        Returns:
            所有新生成的子单元ID集合
        """
        all_new_ids = set()
        for elem_id in elem_ids:
            new_ids = GridExpander.expand_element(grid, elem_id, subdivisions)
            all_new_ids.update(new_ids)
        
        return all_new_ids
    
    @staticmethod
    def expand_with_criterion(grid: Grid3D, criterion_func, subdivisions: int = 2) -> Set[int]:
        """
        基于准则函数自适应细分网格
        
        Args:
            grid: 网格对象
            criterion_func: 判断是否细分的函数(elem_id, elem) -> bool
            subdivisions: 细分参数
            
        Returns:
            所有新生成的子单元ID集合
        """
        to_expand = set()
        for elem_id, elem in grid.elements.items():
            if not elem.get("subdivided", False) and criterion_func(elem_id, elem):
                to_expand.add(elem_id)
        
        return GridExpander.expand_region(grid, to_expand, subdivisions)


class GridCompressor:
    """网格收缩器 - 粗化网格"""
    
    @staticmethod
    def compress_element(grid: Grid3D, parent_elem_id: int) -> Optional[int]:
        """
        收缩单个单元 - 合并其所有子单元
        
        Args:
            grid: 网格对象
            parent_elem_id: 父单元ID
            
        Returns:
            成功返回父单元ID，失败返回None
        """
        if parent_elem_id not in grid.elements:
            logger.warning(f"Element {parent_elem_id} not found")
            return None
        
        parent = grid.elements[parent_elem_id]
        
        if not parent.get("subdivided", False):
            logger.warning(f"Element {parent_elem_id} is not subdivided")
            return None
        
        # 获取所有子单元
        children = parent.get("children", [])
        
        # 删除子单元
        for child_id in children:
            if child_id in grid.elements:
                del grid.elements[child_id]
        
        # 清除细分标记
        parent["subdivided"] = False
        parent.pop("children", None)
        parent["level"] = parent.get("level", 0) - 1
        
        logger.info(f"Compressed element {parent_elem_id} by merging {len(children)} sub-elements")
        return parent_elem_id
    
    @staticmethod
    def compress_region(grid: Grid3D, parent_elem_ids: Set[int]) -> int:
        """
        收缩一个区域内的所有单元
        
        Args:
            grid: 网格对象
            parent_elem_ids: 要收缩的父单元ID集合
            
        Returns:
            成功收缩的单元数量
        """
        count = 0
        for parent_id in parent_elem_ids:
            if GridCompressor.compress_element(grid, parent_id):
                count += 1
        
        return count
    
    @staticmethod
    def compress_with_criterion(grid: Grid3D, criterion_func) -> int:
        """
        基于准则函数自适应粗化网格
        
        Args:
            grid: 网格对象
            criterion_func: 判断是否粗化的函数(elem_id, elem) -> bool
            
        Returns:
            成功收缩的单元数量
        """
        to_compress = set()
        for elem_id, elem in grid.elements.items():
            if elem.get("subdivided", False) and criterion_func(elem_id, elem):
                to_compress.add(elem_id)
        
        return GridCompressor.compress_region(grid, to_compress)
    
    @staticmethod
    def get_coarser_grid(grid: Grid3D) -> Grid3D:
        """
        获取更粗化的网格版本
        
        Args:
            grid: 网格对象
            
        Returns:
            粗化后的新网格
        """
        # 创建新网格副本
        coarse_grid = Grid3D.__new__(Grid3D)
        coarse_grid.resolution = grid.resolution
        coarse_grid.elements = {}
        coarse_grid.nodes = {}
        coarse_grid.adjacency = {}
        
        # 复制所有未被细分的单元
        for elem_id, elem in grid.elements.items():
            if not elem.get("subdivided", False):
                coarse_grid.elements[elem_id] = elem.copy()
        
        # 复制所有节点（节点ID不变）
        for node_id, coord in grid.nodes.items():
            coarse_grid.nodes[node_id] = coord
        
        # 重建邻接关系
        for elem_id in coarse_grid.elements.keys():
            if elem_id in grid.adjacency:
                coarse_grid.adjacency[elem_id] = grid.adjacency[elem_id].copy()
        
        logger.info(f"Generated coarser grid: {len(coarse_grid.elements)} elements")
        return coarse_grid
