# src/api/__init__.py
# API module package initialization.
# Connects to: src/api/app.py, src/api/routes.py
# Created: 2026-09-06

from src.api.app import create_app

__all__ = ["create_app"]
