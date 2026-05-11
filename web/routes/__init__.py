from .api import router as api_router
from .demo import router as demo_router
from .pages import router as pages_router

__all__ = ["api_router", "demo_router", "pages_router"]
