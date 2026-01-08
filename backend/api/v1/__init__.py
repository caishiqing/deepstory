"""
API v1 路由汇总
"""

from fastapi import APIRouter

from .story import router as story_router
from .user import router as user_router
from .prompt import router as prompt_router
from .comment import router as comment_router
from .follow import router as follow_router
from .interaction import router as interaction_router
from .wallet import router as wallet_router
from .pricing import router as pricing_router
from .explore import router as explore_router
from .search import router as search_router

# 创建 v1 API 路由
api_router = APIRouter()

# 注册子路由（按前缀分组）
api_router.include_router(user_router, prefix="/user", tags=["User"])
api_router.include_router(prompt_router, prefix="/prompt", tags=["Prompt"])
api_router.include_router(story_router, prefix="/story", tags=["Story"])

# 社交功能路由（Phase 2）
api_router.include_router(comment_router, tags=["Comment"])
api_router.include_router(follow_router, tags=["Follow"])
api_router.include_router(interaction_router, tags=["Interaction"])

# 商业化功能路由（Phase 3）
api_router.include_router(wallet_router, prefix="/user", tags=["Wallet"])
api_router.include_router(pricing_router, tags=["Pricing"])

# 广场与搜索功能路由（Phase 4）
api_router.include_router(explore_router, prefix="/explore", tags=["Explore"])
api_router.include_router(search_router, prefix="/search", tags=["Search"])
