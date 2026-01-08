"""
故事模块路由 - 核心 SSE 流式接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.models import ApiResponse, StoryCreate, ProgressSave
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.story_service import story_service
from backend.services.progress_service import progress_service

router = APIRouter()


@router.post("/create", response_model=ApiResponse)
async def create_story(
    data: StoryCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    创建故事

    - 基于创意输入（prompt_id）创建新故事
    - 返回 story_id 和 SSE endpoint
    """
    if settings.DATABASE_ENABLED:
        result = await story_service.create_story(session, current_user["user_id"], data)
    else:
        result = await story_service.create_story(current_user["user_id"], data)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.get("/{story_id}", response_model=ApiResponse)
async def get_story(
    story_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取故事详情

    - 返回故事的完整信息
    - 包含标题、封面、状态、统计数据等
    """
    user_id = current_user["user_id"] if current_user else None

    if settings.DATABASE_ENABLED:
        result = await story_service.get_story(session, story_id, user_id)
    else:
        result = await story_service.get_story(story_id, user_id)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.get("/{story_id}/status", response_model=ApiResponse)
async def get_story_status(
    story_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    查询故事生成状态（轻量级接口）

    - 用于前端轮询查询生成进度
    - 返回状态、进度、消息等
    """
    if settings.DATABASE_ENABLED:
        result = await story_service.get_story_status(session, story_id)
    else:
        result = await story_service.get_story_status(story_id)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.get("/{story_id}/stream")
async def stream_story(
    story_id: str,
    from_sequence_id: Optional[str] = Query(None, description="断点续传起点"),
    session: AsyncSession = Depends(get_db_session)
):
    """
    SSE 流式推送故事事件

    - 实时推送故事生成的事件流
    - 支持断点续传（通过 from_sequence_id 参数）
    - 事件格式符合 SSE 规范
    """
    try:
        if settings.DATABASE_ENABLED:
            event_stream = story_service.stream_story(session, story_id, from_sequence_id)
        else:
            event_stream = story_service.stream_story(story_id, from_sequence_id)

        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        logger.error(f"Error streaming story {story_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{story_id}/publish", response_model=ApiResponse)
async def publish_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    发布故事

    - 将草稿状态的故事发布到广场
    - 线性叙事必须完成生成后才能发布
    - 互动叙事可以动态发布
    """
    if settings.DATABASE_ENABLED:
        result = await story_service.publish_story(session, story_id, current_user["user_id"])
    else:
        result = await story_service.publish_story(story_id, current_user["user_id"])

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.post("/{story_id}/progress", response_model=ApiResponse)
async def save_progress(
    story_id: str,
    data: ProgressSave,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    保存用户进度

    - 保存当前播放位置
    - 支持断点续传
    """
    if settings.DATABASE_ENABLED:
        result = await progress_service.save_progress(session, current_user["user_id"], story_id, data)
    else:
        result = await progress_service.save_progress(current_user["user_id"], story_id, data)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.get("/{story_id}/progress", response_model=ApiResponse)
async def get_progress(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取用户进度

    - 返回用户在该故事的播放进度
    - 用于断点续传
    """
    if settings.DATABASE_ENABLED:
        result = await progress_service.get_progress(session, current_user["user_id"], story_id)
    else:
        result = await progress_service.get_progress(current_user["user_id"], story_id)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result
