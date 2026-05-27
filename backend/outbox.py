"""
Outbox pattern implementation for domain events.
Provides a single function to emit events into the outbox table.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import asyncpg

from db import get_asyncpg_connection


async def emit_event(
    event_type: str,
    payload: Dict[str, Any],
    aggregate_type: Optional[str] = None,
    aggregate_id: Optional[str] = None,
    connection: Optional[asyncpg.Connection] = None
) -> str:
    """
    Emit a domain event to the outbox table.
    
    Args:
        event_type: The type of event (e.g., "UserCreated", "OrderPlaced")
        payload: The event data as a dictionary
        aggregate_type: Optional aggregate type (e.g., "User", "Order")
        aggregate_id: Optional aggregate ID
        connection: Optional existing connection to use (for transactions)
    
    Returns:
        The ID of the created outbox entry
    
    Usage:
        await emit_event(
            "InvitationSent",
            {"email": "user@example.com", "role": "member"},
            aggregate_type="Invitation",
            aggregate_id=invitation_id
        )
    """
    # Generate event ID if not in payload
    event_id = str(uuid.uuid4())
    
    # Use provided connection or create a new one
    should_close = False
    if connection is None:
        connection = await get_asyncpg_connection()
        should_close = True
    
    try:
        # Insert into outbox table
        # Note: The exact column names may vary based on the actual schema
        # Using the pattern seen in the codebase
        result = await connection.fetchval(
            """
            INSERT INTO outbox (
                id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5::jsonb, CURRENT_TIMESTAMP
            )
            RETURNING id
            """,
            event_id,
            event_type,
            aggregate_type,
            aggregate_id,
            json.dumps(payload)
        )
        
        # Notify listeners (for real-time processing)
        await connection.execute(
            "NOTIFY outbox_events, $1",
            json.dumps({"id": event_id, "event_type": event_type})
        )
        
        return result
    
    finally:
        if should_close:
            await connection.close()


async def emit_event_in_transaction(
    conn: asyncpg.Connection,
    event_type: str,
    payload: Dict[str, Any],
    aggregate_type: Optional[str] = None,
    aggregate_id: Optional[str] = None
) -> str:
    """
    Emit an event within an existing database transaction.
    
    This is useful when you want to ensure the event is only emitted
    if the entire transaction succeeds.
    
    Args:
        conn: The database connection with active transaction
        event_type: The type of event
        payload: The event data
        aggregate_type: Optional aggregate type
        aggregate_id: Optional aggregate ID
    
    Returns:
        The ID of the created outbox entry
    """
    return await emit_event(
        event_type=event_type,
        payload=payload,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        connection=conn
    )