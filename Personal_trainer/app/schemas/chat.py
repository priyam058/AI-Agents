from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    role: str = "assistant"


class VoiceChatResponse(BaseModel):
    conversation_id: UUID
    transcript: str
    reply_text: str
    audio_url: Optional[str]  # None if ElevenLabs fails (client falls back to text)


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    audio_storage_path: Optional[str]

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    last_message_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    messages: List[MessageResponse]
