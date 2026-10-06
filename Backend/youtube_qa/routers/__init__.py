# Routers package
from .auth_router import router as auth_router
from . import channels, videos, qa, submit

__all__ = ["auth_router", "channels", "videos", "qa", "submit"]