from typing import Optional, List, Any
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    filename: Optional[str] = "file"
    name: Optional[str] = None
    mime_type: Optional[str] = "application/octet-stream"
    data: Optional[str] = None
    data_b64: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.filename and self.name:
            self.filename = self.name
        elif not self.name and self.filename:
            self.name = self.filename
        if not self.data and self.data_b64:
            self.data = self.data_b64
        elif not self.data_b64 and self.data:
            self.data_b64 = self.data


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default", description="Session identifier for user chat context")
    attachments: Optional[List[Attachment]] = Field(default=None, description="Optional uploaded docs, images, video, audio")


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    action_data: Optional[Any] = None
    status: Optional[str] = "done"


class TaskCreateRequest(BaseModel):
    task: str
    session_id: Optional[str] = "default"


class TaskListResponse(BaseModel):
    tasks: List[str] = []
    count: Optional[int] = None
    session_id: Optional[str] = "default"

    def __init__(self, **data):
        if "tasks" in data and ("count" not in data or data["count"] is None):
            data["count"] = len(data["tasks"])
        super().__init__(**data)


class TaskDeleteRequest(BaseModel):
    task_number: int
    session_id: Optional[str] = "default"


class MessageResponse(BaseModel):
    message: str
    status: str = "success"
