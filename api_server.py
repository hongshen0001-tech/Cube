"""
Cube Grid Web API - FastAPI应用
提供RESTful API接口用于网格操作、可视化和下载
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import tempfile
from typing import List, Optional
from pydantic import BaseModel

from grid_3d import Grid3D
from binary_serializer import BinarySerializer
from grid_expander import GridExpander, GridCompressor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Cube Grid System",
    description="3D Cube Grid Generation and Management API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局网格存储
grids_db = {}
next_grid_id = 1


# ==================== 数据模型 ====================

class GridCreateRequest(BaseModel):
    """创建网格请求"""
    resolution: int = 10  # 网格分辨率 1-10


class ExpandRequest(BaseModel):
    """扩散请求"""
    grid_id: int
    elem_ids: Optional[List[int]] = None  # 指定元素ID，为空则全部
    subdivisions: int = 2


class CompressRequest(BaseModel):
    """收缩请求"""
    grid_id: int
    parent_elem_ids: Optional[List[int]] = None


class GridInfo(BaseModel):
    """网格信息"""
    grid_id: int
    resolution: int
    element_count: int
    node_count: int
    boundary_element_count: int
    internal_element_count: int


class ElementInfo(BaseModel):
    """单元信息"""
    elem_id: int
    indices: tuple
    nodes: List[int]
    level: int
    neighbors: dict


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """API文档入口"""
    return {
        "message": "Welcome to Cube Grid System API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.post("/grids", response_model=GridInfo)
async def create_grid(request: GridCreateRequest):
    """创建新网格"""
    global next_grid_id
    
    if request.resolution < 1 or request.resolution > 10:
        raise HTTPException(status_code=400, detail="Resolution must be between 1 and 10")
    
    grid = Grid3D(resolution=request.resolution)
    grid_id = next_grid_id
    next_grid_id += 1
    
    grids_db[grid_id] = grid
    
    logger.info(f"Created grid {grid_id} with resolution {request.resolution}")
    
    return GridInfo(
        grid_id=grid_id,
        resolution=grid.resolution,
        element_count=len(grid.elements),
        node_count=len(grid.nodes),
        boundary_element_count=len(grid.get_boundary_elements()),
        internal_element_count=len(grid.get_internal_elements())
    )


@app.get("/grids/{grid_id}", response_model=GridInfo)
async def get_grid_info(grid_id: int):
    """获取网格信息"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    return GridInfo(
        grid_id=grid_id,
        resolution=grid.resolution,
        element_count=len(grid.elements),
        node_count=len(grid.nodes),
        boundary_element_count=len(grid.get_boundary_elements()),
        internal_element_count=len(grid.get_internal_elements())
    )


@app.get("/grids/{grid_id}/elements/{elem_id}", response_model=ElementInfo)
async def get_element(grid_id: int, elem_id: int):
    """获取单元信息"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    if elem_id not in grid.elements:
        raise HTTPException(status_code=404, detail=f"Element {elem_id} not found")
    
    elem = grid.elements[elem_id]
    neighbors = grid.get_neighbors(elem_id, include_boundary=True)
    
    return ElementInfo(
        elem_id=elem_id,
        indices=elem["indices"],
        nodes=elem["nodes"],
        level=elem.get("level", 0),
        neighbors=neighbors
    )


@app.post("/grids/{grid_id}/expand")
async def expand_grid(grid_id: int, request: ExpandRequest):
    """扩散网格（细分）"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    if request.elem_ids:
        new_ids = GridExpander.expand_region(grid, set(request.elem_ids), request.subdivisions)
    else:
        # 扩散所有未细分的单元
        to_expand = {eid for eid, elem in grid.elements.items() 
                     if not elem.get("subdivided", False)}
        new_ids = GridExpander.expand_region(grid, to_expand, request.subdivisions)
    
    logger.info(f"Expanded grid {grid_id}: {len(new_ids)} new elements")
    
    return {
        "grid_id": grid_id,
        "new_element_ids": list(new_ids),
        "new_element_count": len(new_ids),
        "total_elements": len(grid.elements)
    }


@app.post("/grids/{grid_id}/compress")
async def compress_grid(grid_id: int, request: CompressRequest):
    """收缩网格（粗化）"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    if request.parent_elem_ids:
        count = GridCompressor.compress_region(grid, set(request.parent_elem_ids))
    else:
        # 压缩所有已细分的单元
        count = GridCompressor.compress_with_criterion(
            grid,
            lambda eid, elem: elem.get("subdivided", False)
        )
    
    logger.info(f"Compressed grid {grid_id}: {count} elements")
    
    return {
        "grid_id": grid_id,
        "compressed_count": count,
        "total_elements": len(grid.elements)
    }


@app.post("/grids/{grid_id}/export/binary")
async def export_binary(grid_id: int):
    """导出网格为二进制文件"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".cube") as tmp:
        tmp_path = tmp.name
    
    try:
        BinarySerializer.save_to_file(grid, tmp_path)
        return FileResponse(
            tmp_path,
            media_type="application/octet-stream",
            filename=f"grid_{grid_id}.cube"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/grids/import/binary")
async def import_binary(file: UploadFile = File(...)):
    """导入网格从二进制文件"""
    global next_grid_id
    
    try:
        # 读取上传的文件
        content = await file.read()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # 反序列化
        grid = BinarySerializer.load_from_file(tmp_path)
        os.unlink(tmp_path)
        
        # 存储网格
        grid_id = next_grid_id
        next_grid_id += 1
        grids_db[grid_id] = grid
        
        logger.info(f"Imported grid {grid_id} from binary file")
        
        return GridInfo(
            grid_id=grid_id,
            resolution=grid.resolution,
            element_count=len(grid.elements),
            node_count=len(grid.nodes),
            boundary_element_count=len(grid.get_boundary_elements()),
            internal_element_count=len(grid.get_internal_elements())
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import grid: {str(e)}")


@app.get("/grids/{grid_id}/export/json")
async def export_json(grid_id: int):
    """导出网格为JSON格式"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    grid = grids_db[grid_id]
    
    return {
        "grid_id": grid_id,
        "resolution": grid.resolution,
        "elements": {
            str(eid): {
                "indices": elem["indices"],
                "nodes": elem["nodes"],
                "level": elem.get("level", 0)
            }
            for eid, elem in grid.elements.items()
        },
        "nodes": {
            str(nid): coord
            for nid, coord in grid.nodes.items()
        },
        "adjacency": {
            str(eid): neighbors
            for eid, neighbors in grid.adjacency.items()
        }
    }


@app.delete("/grids/{grid_id}")
async def delete_grid(grid_id: int):
    """删除网格"""
    if grid_id not in grids_db:
        raise HTTPException(status_code=404, detail=f"Grid {grid_id} not found")
    
    del grids_db[grid_id]
    
    logger.info(f"Deleted grid {grid_id}")
    
    return {"message": f"Grid {grid_id} deleted"}


@app.get("/grids")
async def list_grids():
    """列表所有网格"""
    return {
        "grids": [
            {
                "grid_id": gid,
                "resolution": grid.resolution,
                "element_count": len(grid.elements),
                "node_count": len(grid.nodes)
            }
            for gid, grid in grids_db.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
