"""
创意模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse, PromptCreate, PromptUpdate
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.db.dao import PromptDAO

router = APIRouter()


@router.post("/create", response_model=ApiResponse)
async def create_prompt(
    data: PromptCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    创建创意

    - 保存用户的创意输入
    - 返回 prompt_id，用于后续创建故事
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    # 创建创意
    prompt = await PromptDAO.create(
        session=session,
        user_id=current_user["user_id"],
        logline=data.logline,
        characters=[],  # 需要从 character_inputs 提取
        character_inputs=data.characters,
        relationships=data.relationships,
        themes=data.themes.model_dump()
    )

    return ApiResponse(
        success=True,
        message="Prompt created",
        data={
            "prompt_id": prompt.id,
            "logline": prompt.logline,
            "created_at": prompt.created_at.isoformat(),
        }
    )


@router.get("/{prompt_id}", response_model=ApiResponse)
async def get_prompt(
    prompt_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取创意详情

    - 返回创意的完整信息
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    prompt = await PromptDAO.get_by_id(session, prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROMPT_NOT_FOUND", "message": "创意不存在"}
        )

    # 检查权限
    if prompt.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PERMISSION_DENIED", "message": "无权限访问"}
        )

    return ApiResponse(
        success=True,
        data={
            "prompt_id": prompt.id,
            "logline": prompt.logline,
            "characters": prompt.character_inputs,
            "relationships": prompt.relationships,
            "themes": prompt.themes,
            "created_at": prompt.created_at.isoformat(),
            "updated_at": prompt.updated_at.isoformat(),
        }
    )


@router.patch("/{prompt_id}", response_model=ApiResponse)
async def update_prompt(
    prompt_id: str,
    data: PromptUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    更新创意

    - 修改创意的内容
    - 只有创建者可以修改
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    prompt = await PromptDAO.get_by_id(session, prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROMPT_NOT_FOUND", "message": "创意不存在"}
        )

    # 检查权限
    if prompt.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PERMISSION_DENIED", "message": "无权限修改"}
        )

    # 更新创意
    update_data = data.model_dump(exclude_unset=True)
    themes = update_data.pop("themes", None)
    if themes:
        update_data["themes"] = themes.model_dump()

    success = await PromptDAO.update(
        session=session,
        prompt_id=prompt_id,
        **update_data
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "UPDATE_FAILED", "message": "更新失败"}
        )

    return ApiResponse(
        success=True,
        message="Prompt updated"
    )


@router.get("/user/list", response_model=ApiResponse)
async def list_user_prompts(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    获取用户的创意列表

    - 分页返回用户创建的所有创意
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    prompts = await PromptDAO.get_user_prompts(
        session=session,
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset
    )

    return ApiResponse(
        success=True,
        data={
            "prompts": [
                {
                    "prompt_id": p.id,
                    "logline": p.logline,
                    "created_at": p.created_at.isoformat(),
                }
                for p in prompts
            ],
            "total": len(prompts),
            "limit": limit,
            "offset": offset,
        }
    )
