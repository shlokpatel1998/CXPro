"""
Database connection factories for Supabase and asyncpg.
Provides a narrow public API for database access.
"""

import os
from typing import Optional, Dict, Any
import asyncpg
from asyncpg.pool import Pool
from dotenv import load_dotenv
from pathlib import Path


# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try .env.local
    env_path = Path(__file__).parent.parent / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)


# Private: Cached connection pool
_connection_pool: Optional[Pool] = None


async def get_asyncpg_connection() -> asyncpg.Connection:
    """
    Get a single asyncpg connection.
    Use this for one-off operations.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    return await asyncpg.connect(database_url)


async def get_asyncpg_pool(min_size: int = 1, max_size: int = 5) -> Pool:
    """
    Get or create an asyncpg connection pool.
    Use this for long-running services.
    """
    global _connection_pool
    
    if _connection_pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        _connection_pool = await asyncpg.create_pool(
            database_url,
            min_size=min_size,
            max_size=max_size
        )
    
    return _connection_pool


async def close_pool():
    """Close the connection pool if it exists."""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None


def get_database_url() -> str:
    """Get the database URL from environment."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return database_url


# Note: Supabase client creation would go here if we were using the Supabase SDK
# For now, this codebase uses raw asyncpg for all database operations
# If Supabase SDK is needed in future, add:
# def create_supabase_client() -> Client:
#     """Create and return a Supabase client."""
#     url = os.getenv("SUPABASE_URL")
#     key = os.getenv("SUPABASE_ANON_KEY")
#     if not url or not key:
#         raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
#     from supabase import create_client, Client
#     return create_client(url, key)