from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.conversation import PTConversation, PTMessage
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationSummary,
    MessageResponse,
    VoiceChatResponse,
)
from app.services.claude_service import chat_with_pt
from app.services.profile_service import decrypt_profile_for_prompt

router = APIRouter()

_MAX_CONTEXT_MESSAGES = 20  # number of prior messages sent to Claude for context


async def _get_or_create_conversation(
    conversation_id: Optional[UUID], user_id: UUID, db: AsyncSession
) -> PTConversation:
    if conversation_id:
        result = await db.execute(
            select(PTConversation).where(
                PTConversation.id == conversation_id,
                PTConversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv

    conv = PTConversation(user_id=user_id)
    db.add(conv)
    await db.flush()
    return conv


async def _build_history(conversation_id: UUID, db: AsyncSession) -> List[dict]:
    result = await db.execute(
        select(PTMessage)
        .where(PTMessage.conversation_id == conversation_id)
        .order_by(PTMessage.created_at.desc())
        .limit(_MAX_CONTEXT_MESSAGES)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


async def _get_profile_context(user_id: UUID, db: AsyncSession) -> dict:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return {"workout_level": "Beginner", "goal": "general fitness", "injuries": "none",
                "age": "unknown", "weight_kg": "unknown", "height_cm": "unknown"}
    return decrypt_profile_for_prompt(profile)


@router.post("/text", response_model=ChatResponse)
async def text_chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_or_create_conversation(body.conversation_id, current_user.id, db)
    history = await _build_history(conv.id, db)
    profile_ctx = await _get_profile_context(current_user.id, db)

    reply = await chat_with_pt(profile_ctx, history, body.message)

    db.add(PTMessage(conversation_id=conv.id, role="user", content=body.message))
    db.add(PTMessage(conversation_id=conv.id, role="assistant", content=reply))
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()

    return ChatResponse(conversation_id=conv.id, reply=reply)


@router.post("/voice", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(..., description="Audio file (webm, mp4, wav, mpeg)"),
    conversation_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.whisper_service import transcribe_audio
    from app.services.elevenlabs_service import synthesize_speech

    # Validate file type
    allowed_types = {"audio/webm", "audio/mp4", "audio/wav", "audio/mpeg", "audio/ogg"}
    if audio.content_type and audio.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail=f"Unsupported audio format: {audio.content_type}")

    # Validate size
    audio_bytes = await audio.read()
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Audio exceeds {settings.max_audio_size_mb}MB limit")

    # Step 1: Transcribe
    try:
        transcript = transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not transcribe audio: {str(e)}")

    # Step 2: Get conversation + profile
    conv_uuid = UUID(conversation_id) if conversation_id else None
    conv = await _get_or_create_conversation(conv_uuid, current_user.id, db)
    history = await _build_history(conv.id, db)
    profile_ctx = await _get_profile_context(current_user.id, db)

    # Step 3: Claude response
    try:
        reply_text = await chat_with_pt(profile_ctx, history, transcript)
    except Exception as e:
        db.add(PTMessage(conversation_id=conv.id, role="user", content=transcript))
        await db.commit()
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {str(e)}")

    # Step 4: Save messages
    user_msg = PTMessage(conversation_id=conv.id, role="user", content=transcript)
    assistant_msg = PTMessage(conversation_id=conv.id, role="assistant", content=reply_text)
    db.add(user_msg)
    db.add(assistant_msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    # Step 5: TTS + Storage
    audio_url = None
    try:
        mp3_bytes = synthesize_speech(reply_text)
        audio_url = await _upload_to_supabase(mp3_bytes, current_user.id, assistant_msg.id)
        assistant_msg.audio_storage_path = f"responses/{current_user.id}/{assistant_msg.id}.mp3"
    except Exception:
        pass  # Graceful degradation — return text without audio

    await db.commit()

    return VoiceChatResponse(
        conversation_id=conv.id,
        transcript=transcript,
        reply_text=reply_text,
        audio_url=audio_url,
    )


async def _upload_to_supabase(mp3_bytes: bytes, user_id: UUID, message_id: UUID) -> Optional[str]:
    from supabase import create_client
    from app.core.config import settings

    if not settings.supabase_url or not settings.supabase_service_key:
        return None

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    path = f"responses/{user_id}/{message_id}.mp3"
    client.storage.from_("voice-responses").upload(
        path,
        mp3_bytes,
        file_options={"content-type": "audio/mpeg"},
    )
    signed = client.storage.from_("voice-responses").create_signed_url(path, expires_in=3600)
    return signed.get("signedURL")


@router.get("/history", response_model=List[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PTConversation)
        .where(PTConversation.user_id == current_user.id)
        .order_by(PTConversation.last_message_at.desc())
    )
    convs = result.scalars().all()
    return [ConversationSummary.model_validate(c) for c in convs]


@router.get("/history/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_result = await db.execute(
        select(PTConversation).where(
            PTConversation.id == conversation_id,
            PTConversation.user_id == current_user.id,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(PTMessage)
        .where(PTMessage.conversation_id == conversation_id)
        .order_by(PTMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return ConversationHistoryResponse(messages=[MessageResponse.model_validate(m) for m in messages])


@router.delete("/history/{conversation_id}", status_code=200)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_result = await db.execute(
        select(PTConversation).where(
            PTConversation.id == conversation_id,
            PTConversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.execute(delete(PTMessage).where(PTMessage.conversation_id == conversation_id))
    await db.delete(conv)
    await db.commit()
    return {"message": "conversation deleted"}
