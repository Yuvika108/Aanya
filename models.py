import os
import sys

# Ensure server package directory is accessible
_server_dir = os.path.join(os.path.dirname(__file__), "server")
if _server_dir not in sys.path:
    sys.path.append(_server_dir)

from server.models import (
    ChatRequest,
    ChatResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskDeleteRequest,
    MessageResponse,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "TaskCreateRequest",
    "TaskListResponse",
    "TaskDeleteRequest",
    "MessageResponse",
]
