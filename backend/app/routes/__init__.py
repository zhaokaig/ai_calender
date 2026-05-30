from .auth import auth_bp
from .events import events_bp
from .health import health_bp
from .transcriptions import transcriptions_bp
from .voice_command import voice_command_bp

__all__ = ["auth_bp", "events_bp", "health_bp", "transcriptions_bp", "voice_command_bp"]
