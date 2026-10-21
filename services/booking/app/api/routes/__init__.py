"""Routes export for booking service."""

from app.api.routes import health, holds, inventory, seats

__all__ = ["health", "holds", "inventory", "seats"]
