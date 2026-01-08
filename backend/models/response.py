"""
统一响应模型
"""

from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel, Field


T = TypeVar('T')


class PaginationMeta(BaseModel):
    """分页元数据"""
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    total: int = Field(..., description="总数")


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    success: bool = Field(True, description="请求是否成功")
    data: Optional[T] = Field(None, description="响应数据")
    message: Optional[str] = Field(None, description="响应消息")
    code: Optional[int] = Field(None, description="业务错误码")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"key": "value"},
                "message": "操作成功"
            }
        }


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(False, description="请求失败")
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")
    error: Optional[dict] = Field(None, description="错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "code": 400,
                "message": "请求参数错误",
                "error": {
                    "type": "VALIDATION_ERROR",
                    "details": [
                        {
                            "field": "user_id",
                            "message": "用户ID不能为空"
                        }
                    ]
                }
            }
        }
