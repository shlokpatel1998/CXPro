#!/usr/bin/env python3
"""
Deep module for Role/Permission administration and Membership lifecycle.
Consolidates roles.py and the administrative side of permissions.py.
"""

from typing import Optional
import asyncpg

from db import get_asyncpg_connection


ROLES = (
    'OCA',
    'CM',
    'cx_engineer',
    'field_technician',
    'design_engineer',
    'owner_fm'
)

ROLE_LABELS = {
    'OCA': "Owner's Commissioning Agent",
    'CM': 'Construction Manager',
    'cx_engineer': 'Commissioning Engineer',
    'field_technician': 'Field Technician',
    'design_engineer': 'Design Engineer',
    'owner_fm': 'Owner/Facility Manager'
}


def is_valid_role(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    return s in ROLES


def can_manage_team(role: str) -> bool:
    if not role or not isinstance(role, str):
        return False
    return role in ('OCA', 'CM')


def can_create_project(role: str) -> bool:
    if not role or not isinstance(role, str):
        return False
    return role in ('OCA', 'CM')


async def get_membership(
    user_id: str,
    org_id: str,
    connection: Optional[asyncpg.Connection] = None
) -> Optional[dict]:
    should_close = False
    if connection is None:
        connection = await get_asyncpg_connection()
        should_close = True

    try:
        row = await connection.fetchrow(
            "SELECT id, user_id, org_id, role, created_at FROM memberships WHERE user_id = $1 AND org_id = $2",
            user_id, org_id
        )
        return dict(row) if row else None
    finally:
        if should_close:
            await connection.close()
