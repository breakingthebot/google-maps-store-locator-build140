# src/config.py
# Application runtime settings and environment variable parser.
# Connects to: src/services/, src/api/, src/cli/
# Created: 2026-09-06

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str = "Google Maps Store Locator"
    app_version: str = "1.0.0"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Google Maps Platform configuration
    google_maps_api_key: Optional[str] = None

    # Geospatial defaults
    default_latitude: float = 37.774929
    default_longitude: float = -122.419416
    default_search_radius_km: float = 25.0
    max_search_radius_km: float = 100.0

    # Persistence
    database_path: str = "storage/store_locator.db"

    @property
    def is_live_google_maps_enabled(self) -> bool:
        """Return True if a non-empty Google Maps API key is configured."""
        return bool(self.google_maps_api_key and self.google_maps_api_key.strip())

    @property
    def resolved_db_path(self) -> Path:
        """Resolve the SQLite database path ensuring parent directory existence."""
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Global singleton settings instance
settings = Settings()
