"""Typed Firestore document models (Pydantic v2) for the OffGrid AI backend.

Every collection listed in Implementation Plan §6.1 has a matching module
here. Import from the submodules directly in application code
(`from models.sku import SKU`); this `__init__` just re-exports the most
commonly used names for convenience.
"""

from models.common import EventType, ImportStatus, SignalType
from models.event import Event
from models.session import CartItem, Session, StructuredIntent
from models.sku import SKU

__all__ = [
    "SKU",
    "Session",
    "CartItem",
    "StructuredIntent",
    "Event",
    "EventType",
    "SignalType",
    "ImportStatus",
]
