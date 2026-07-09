import os
from flask_socketio import SocketIO
from supabase import create_client, Client

socketio = SocketIO()

_supabase_client: Client | None = None


def get_supabase() -> Client:
    """
    Lazily creates and caches the Supabase client.
    Reads SUPABASE_URL / SUPABASE_KEY from the environment (set as Render
    environment variables in production, or a local .env file in dev).
    """
    global _supabase_client
    if _supabase_client is None:
        url = (os.environ.get("SUPABASE_URL") or "").strip()
        key = (os.environ.get("SUPABASE_KEY") or "").strip()
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set as environment variables."
            )
        if not url.startswith("https://"):
            raise RuntimeError(
                f"SUPABASE_URL looks malformed after stripping whitespace: {url!r}"
            )
        _supabase_client = create_client(url, key)
    return _supabase_client
