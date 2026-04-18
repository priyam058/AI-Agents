"""Admin endpoints — internal maintenance tasks, not exposed to regular users."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings

router = APIRouter()


@router.post("/cleanup-audio", tags=["admin"])
async def cleanup_old_audio(x_admin_key: str = Header(...)):
    """
    Delete voice-response MP3 files older than 24 hours from Supabase Storage.
    Protected by a static admin key set in the environment.
    Call this on a schedule (e.g. daily via Railway cron or an external cron job).
    """
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    import asyncio
    deleted, errors = await asyncio.to_thread(_cleanup_sync)

    return {"deleted": deleted, "errors": errors}


def _cleanup_sync() -> tuple[int, int]:
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    bucket = client.storage.from_("voice-responses")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    deleted = 0
    errors = 0

    # List all top-level "folders" (user IDs)
    try:
        folders = bucket.list("")
    except Exception:
        return 0, 1

    for folder in folders:
        folder_name = folder.get("name", "")
        if not folder_name:
            continue

        try:
            files = bucket.list(folder_name)
        except Exception:
            errors += 1
            continue

        to_delete = []
        for f in files:
            created_raw = f.get("created_at") or f.get("updated_at")
            if not created_raw:
                continue
            # Supabase returns ISO 8601 strings
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if created_at < cutoff:
                to_delete.append(f"{folder_name}/{f['name']}")

        if to_delete:
            try:
                bucket.remove(to_delete)
                deleted += len(to_delete)
            except Exception:
                errors += len(to_delete)

    return deleted, errors
