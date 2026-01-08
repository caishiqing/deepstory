"""
API 路由模块
"""

from fastapi import APIRouter
from .v1 import api_router as api_v1_router

__all__ = ["api_v1_router"]
