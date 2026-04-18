from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/personal_trainer"

    # JWT
    jwt_secret: str = "changeme-use-a-long-random-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Encryption (base64-encoded 32-byte key)
    encryption_key: str = ""

    # AI Services
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel"

    # Supabase Storage
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Google OAuth
    google_client_id: str = ""

    # Email (password reset via Resend)
    resend_api_key: str = ""
    resend_from_email: str = "noreply@yourdomain.com"

    # Frontend URL (used in password reset links)
    frontend_url: str = "http://localhost:3000"

    # Password reset
    password_reset_expire_minutes: int = 60

    # Admin
    admin_key: str = "changeme-set-a-strong-random-key"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Limits
    max_audio_size_mb: int = 25

    # Environment
    environment: str = "development"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
