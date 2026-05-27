#!/usr/bin/env python3
"""
Deep module for invitation lifecycle management.
Consolidates invitation creation, resending, and redemption logic.
"""

import secrets
import os
from typing import Optional, Dict, Any, Union, Literal
from datetime import datetime, timedelta, timezone
import uuid
from dataclasses import dataclass
from fastapi import HTTPException
import asyncpg

from db import get_asyncpg_connection
from auth import require_permission
from outbox import emit_event


# The 6 canonical role string values from docs/architecture.md
ROLES = (
    'OCA',
    'CM',
    'cx_engineer',
    'field_technician',
    'design_engineer',
    'owner_fm'
)

# Display labels for each role
ROLE_LABELS = {
    'OCA': "Owner's Commissioning Agent",
    'CM': 'Construction Manager',
    'cx_engineer': 'Commissioning Engineer',
    'field_technician': 'Field Technician',
    'design_engineer': 'Design Engineer',
    'owner_fm': 'Owner/Facility Manager'
}


def is_valid_role(s: str) -> bool:
    """
    Check if a string is a valid role value.
    
    Args:
        s: String to validate
        
    Returns:
        True if s is one of the 6 valid role values, False otherwise.
        Returns False for None, empty string, or invalid values.
    """
    if not s or not isinstance(s, str):
        return False
    return s in ROLES


def can_manage_team(role: str) -> bool:
    """
    Check if a role has permission to manage team members.
    
    Args:
        role: Role string to check
        
    Returns:
        True if role is 'OCA' or 'CM', False otherwise.
        Returns False for None, empty string, and unknown roles.
    """
    if not role or not isinstance(role, str):
        return False
    return role in ('OCA', 'CM')


# InviteDecision pure module components
@dataclass
class ExistingInvite:
    """Represents an existing pending invitation row."""
    email: str
    project_id: str
    expires_at: datetime
    send_count: int
    accepted_at: Optional[datetime] = None


@dataclass 
class CreateNew:
    """Action: Create a new invitation."""
    action: Literal["create_new"] = "create_new"


@dataclass
class ReplaceExpired:
    """Action: Replace an expired invitation."""
    action: Literal["replace_expired"] = "replace_expired"


@dataclass
class IncrementResend:
    """Action: Increment resend count on existing invitation."""
    new_count: int
    action: Literal["increment_resend"] = "increment_resend"


@dataclass
class RejectCapReached:
    """Action: Reject because cap is reached."""
    action: Literal["reject_cap_reached"] = "reject_cap_reached"


Action = Union[CreateNew, ReplaceExpired, IncrementResend, RejectCapReached]


def decide_invite_action(
    existing_row: Optional[ExistingInvite],
    now: datetime,
    cap: int = 3
) -> Action:
    """
    Determine the appropriate action for an invitation request.
    
    Args:
        existing_row: Existing pending invitation if one exists
        now: Current datetime for expiration checks  
        cap: Maximum send count allowed (default 3)
        
    Returns:
        Action indicating what should be done
        
    Raises:
        ValueError: If existing_row has accepted_at set (service layer should filter this)
    """
    # No existing row - create new
    if existing_row is None:
        return CreateNew()
    
    # Sanity check - service layer should never pass accepted invites
    if existing_row.accepted_at is not None:
        raise ValueError(
            "decide_invite_action should not be called with accepted invitations. "
            "The service layer should filter these out."
        )
    
    # Check if expired
    if existing_row.expires_at < now:
        return ReplaceExpired()
    
    # Active invitation - check send count
    if existing_row.send_count < cap:
        return IncrementResend(new_count=existing_row.send_count + 1)
    else:
        return RejectCapReached()


# Public API functions
async def send_invite(
    email: str,
    org_id: str,
    project_id: str,
    role: str,
    discipline_scope_id: str,
    invited_by: str,
    supabase_client: Any = None,
    connection: Optional[asyncpg.Connection] = None
) -> Dict[str, Any]:
    """
    Send a new invitation.
    
    This is the main entry point for creating invitations. It handles:
    - Role validation
    - Permission checking
    - Token generation
    - Database insertion
    - Email sending (via Supabase)
    
    Args:
        email: Email address of the invitee
        org_id: Organization ID
        project_id: Project ID
        role: Role to grant (must be one of the 6 valid roles)
        discipline_scope_id: Discipline scope ID
        invited_by: User ID of the inviter
        supabase_client: Supabase client for auth operations
        connection: Optional asyncpg connection (will create one if not provided)
    
    Returns:
        Dict with invitation ID and success flag
        
    Raises:
        HTTPException: If inviter cannot manage team or role is invalid
    """
    # Validate the role
    if not is_valid_role(role):
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    # Use provided connection or create new one
    should_close = False
    if connection is None:
        connection = await get_asyncpg_connection()
        should_close = True
    
    try:
        # Verify caller can manage the team
        caller_role = await _get_user_role(invited_by, org_id, connection)
        if not can_manage_team(caller_role):
            raise HTTPException(status_code=403, detail="You do not have permission to invite users to the organization")
        
        # Generate a secure token
        token = secrets.token_urlsafe(32)
        
        # Construct the redirect URL
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        redirect_to = f"{frontend_url}/accept-invite?token={token}"
        
        # Create pending invitation in database
        invitation_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=7)
        
        await connection.execute("""
            INSERT INTO pending_invitations (
                id, email, org_id, project_id, role, discipline_scope_id,
                token, invited_by, expires_at, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, invitation_id, email, org_id, project_id, role, discipline_scope_id,
            token, invited_by, expires_at, datetime.now())
        
        # Emit domain event
        await emit_event(
            event_type="InvitationSent",
            payload={
                "invitation_id": invitation_id,
                "email": email,
                "org_id": org_id,
                "project_id": project_id,
                "role": role,
                "invited_by": invited_by
            },
            aggregate_type="Invitation",
            aggregate_id=invitation_id,
            connection=connection
        )
        
        # Send email if Supabase client is provided
        if supabase_client:
            # Check if user exists
            existing = await connection.fetchrow(
                "SELECT id FROM users WHERE email = $1", email
            )
            user_exists = existing is not None
            
            # Send the magic-link email through Supabase Auth
            if not user_exists:
                supabase_client.auth.admin.invite_user_by_email(
                    email,
                    {"redirect_to": redirect_to},
                )
            else:
                supabase_client.auth.sign_in_with_otp({
                    "email": email,
                    "options": {"email_redirect_to": redirect_to},
                })
        
        return {
            'id': invitation_id,
            'success': True
        }
    
    finally:
        if should_close:
            await connection.close()


async def resend_invite(
    email: str,
    project_id: str,
    invited_by: str,
    supabase_client: Any = None,
    connection: Optional[asyncpg.Connection] = None
) -> Dict[str, Any]:
    """
    Resend an existing invitation.
    
    Uses the InviteDecision logic to determine whether to:
    - Increment the resend count
    - Replace an expired invitation
    - Reject if cap is reached
    
    Args:
        email: Email address of the invitee
        project_id: Project ID
        invited_by: User ID requesting the resend
        supabase_client: Supabase client for auth operations
        connection: Optional asyncpg connection
    
    Returns:
        Dict with success flag and action taken
        
    Raises:
        HTTPException: If resend cap is reached or other errors
    """
    # Use provided connection or create new one
    should_close = False
    if connection is None:
        connection = await get_asyncpg_connection()
        should_close = True
    
    try:
        # Look up existing invitation
        existing_row = await connection.fetchrow("""
            SELECT id, email, project_id, org_id, role, discipline_scope_id,
                   expires_at, send_count, accepted_at, invited_by, token
            FROM pending_invitations
            WHERE email = $1 AND project_id = $2
            ORDER BY created_at DESC
            LIMIT 1
        """, email, project_id)
        
        # Convert to ExistingInvite if found
        existing = None
        if existing_row:
            existing = ExistingInvite(
                email=existing_row['email'],
                project_id=existing_row['project_id'],
                expires_at=existing_row['expires_at'],
                send_count=existing_row['send_count'],
                accepted_at=existing_row['accepted_at']
            )
        
        # Decide what action to take
        now = datetime.now(timezone.utc)
        action = decide_invite_action(existing, now)
        
        if isinstance(action, RejectCapReached):
            raise HTTPException(status_code=429, detail="Resend limit reached for this invitation")
        
        elif isinstance(action, CreateNew):
            # Should not happen in resend flow
            raise HTTPException(status_code=404, detail="No existing invitation found")
        
        elif isinstance(action, ReplaceExpired):
            # Create new invitation replacing the expired one
            return await send_invite(
                email=existing_row['email'],
                org_id=existing_row['org_id'],
                project_id=existing_row['project_id'],
                role=existing_row['role'],
                discipline_scope_id=existing_row['discipline_scope_id'],
                invited_by=invited_by,
                supabase_client=supabase_client,
                connection=connection
            )
        
        elif isinstance(action, IncrementResend):
            # Update send count
            await connection.execute("""
                UPDATE pending_invitations
                SET send_count = $1, updated_at = $2
                WHERE id = $3
            """, action.new_count, datetime.now(), existing_row['id'])
            
            # Resend email if Supabase client provided
            if supabase_client:
                frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
                redirect_to = f"{frontend_url}/accept-invite?token={existing_row['token']}"
                
                # Check if user exists
                user_exists_row = await connection.fetchrow(
                    "SELECT id FROM users WHERE email = $1", email
                )
                user_exists = user_exists_row is not None
                
                if not user_exists:
                    supabase_client.auth.admin.invite_user_by_email(
                        email,
                        {"redirect_to": redirect_to},
                    )
                else:
                    supabase_client.auth.sign_in_with_otp({
                        "email": email,
                        "options": {"email_redirect_to": redirect_to},
                    })
            
            # Emit event
            await emit_event(
                event_type="InvitationResent",
                payload={
                    "invitation_id": existing_row['id'],
                    "email": email,
                    "send_count": action.new_count,
                    "resent_by": invited_by
                },
                aggregate_type="Invitation",
                aggregate_id=existing_row['id'],
                connection=connection
            )
            
            return {
                'success': True,
                'action': 'resent',
                'send_count': action.new_count
            }
    
    finally:
        if should_close:
            await connection.close()


async def redeem_invite(
    token: str,
    user_id: str,
    connection: Optional[asyncpg.Connection] = None
) -> Dict[str, Any]:
    """
    Redeem an invitation token.
    
    This function is called when a user clicks the invitation link.
    It validates the token, creates the membership, and marks the invitation as accepted.
    
    Args:
        token: The invitation token from the URL
        user_id: The authenticated user's ID
        connection: Optional asyncpg connection
    
    Returns:
        Dict with success flag and membership details
        
    Raises:
        HTTPException: If token is invalid, expired, or already used
    """
    # Use provided connection or create new one
    should_close = False
    if connection is None:
        connection = await get_asyncpg_connection()
        should_close = True
    
    try:
        # Start transaction
        async with connection.transaction():
            # Look up invitation by token
            invitation = await connection.fetchrow("""
                SELECT id, email, org_id, project_id, role, discipline_scope_id,
                       expires_at, accepted_at
                FROM pending_invitations
                WHERE token = $1
            """, token)
            
            if not invitation:
                raise HTTPException(status_code=404, detail="Invalid invitation token")
            
            # Check if already accepted
            if invitation['accepted_at'] is not None:
                raise HTTPException(status_code=400, detail="Invitation has already been accepted")
            
            # Check if expired
            if invitation['expires_at'] < datetime.now():
                raise HTTPException(status_code=400, detail="Invitation has expired")
            
            # Create membership
            membership_id = str(uuid.uuid4())
            await connection.execute("""
                INSERT INTO memberships (
                    id, user_id, org_id, role, created_at
                ) VALUES ($1, $2, $3, $4, $5)
            """, membership_id, user_id, invitation['org_id'], invitation['role'], datetime.now())
            
            # Create participation (project assignment)
            participation_id = str(uuid.uuid4())
            await connection.execute("""
                INSERT INTO participations (
                    id, user_id, project_id, role, discipline_scope_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """, participation_id, user_id, invitation['project_id'], 
                invitation['role'], invitation['discipline_scope_id'], datetime.now())
            
            # Mark invitation as accepted
            await connection.execute("""
                UPDATE pending_invitations
                SET accepted_at = $1, accepted_by = $2, updated_at = $1
                WHERE id = $3
            """, datetime.now(), user_id, invitation['id'])
            
            # Emit event
            await emit_event(
                event_type="InvitationAccepted",
                payload={
                    "invitation_id": invitation['id'],
                    "user_id": user_id,
                    "org_id": invitation['org_id'],
                    "project_id": invitation['project_id'],
                    "role": invitation['role']
                },
                aggregate_type="Invitation",
                aggregate_id=invitation['id'],
                connection=connection
            )
            
            return {
                'success': True,
                'membership_id': membership_id,
                'participation_id': participation_id,
                'org_id': invitation['org_id'],
                'project_id': invitation['project_id'],
                'role': invitation['role']
            }
    
    finally:
        if should_close:
            await connection.close()


# Private helper functions
async def _get_user_role(user_id: str, org_id: str, connection: asyncpg.Connection) -> Optional[str]:
    """
    Get the role of a user in the given organization.
    
    Args:
        user_id: User ID to check
        org_id: Organization ID
        connection: Database connection
        
    Returns:
        User's role string if found, None otherwise
    """
    result = await connection.fetchrow("""
        SELECT role FROM memberships 
        WHERE user_id = $1 AND org_id = $2
    """, user_id, org_id)
    
    return result['role'] if result else None