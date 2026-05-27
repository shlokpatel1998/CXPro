#!/usr/bin/env python3
"""
Simple test to verify invitation module works
"""

import pytest
from contexts.identity_access.invitations import send_invite, can_manage_team
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
import secrets


def test_invitation_module_imports():
    """Test that invitation functions can be imported"""
    assert send_invite is not None
    assert can_manage_team is not None
    print("✅ Invitation module imports successfully")


async def test_create_invitation_basic():
    """Test basic invitation creation logic"""
    # Mock Supabase client
    mock_supabase = MagicMock()
    mock_auth_admin = MagicMock()
    mock_auth = MagicMock()
    mock_supabase.auth.admin = mock_auth_admin
    mock_supabase.auth = mock_auth
    
    # Mock database connection
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.fetchrow = AsyncMock(side_effect=[
        {'role': 'OCA'},  # First call: get user role
        None  # Second call: check if user exists
    ])
    
    # Mock auth check - user doesn't exist
    mock_auth.get_user = MagicMock(side_effect=Exception("User not found"))
    mock_auth_admin.invite_user_by_email = MagicMock(return_value={"user": {"id": "new-id"}})
    
    # Test create invitation
    result = await send_invite(
        email='test@example.com',
        org_id='org-123',
        project_id='proj-456',
        role='cx_engineer',
        discipline_scope_id='disc-789',
        invited_by='inviter-999',
        supabase_client=mock_supabase,
        connection=mock_conn
    )
    
    # Verify result
    assert result['success'] == True
    assert 'id' in result
    
    # Verify database was called to insert invitation
    mock_conn.execute.assert_called()
    
    # Debug: check what was called
    print(f"mock_auth_admin calls: {mock_auth_admin.method_calls}")
    print(f"mock_auth calls: {mock_auth.method_calls}")
    
    # Verify database was called properly
    assert mock_conn.execute.called
    
    print("✅ Basic invitation creation test passed")


async def test_non_manager_forbidden():
    """Test that non-manager users cannot create invitations"""
    # Mock Supabase client
    mock_supabase = MagicMock()
    
    # Mock database connection - user is not OCA or CM
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={'role': 'cx_engineer'})
    
    # Test should raise 403
    try:
        await send_invite(
            email='test@example.com',
            org_id='org-123',
            project_id='proj-456',
            role='cx_engineer',
            discipline_scope_id='disc-789',
            invited_by='non-manager-user',
            supabase_client=mock_supabase,
            connection=mock_conn
        )
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 403
        print("✅ Non-manager forbidden test passed")


if __name__ == "__main__":
    import asyncio
    
    # Run tests
    test_invitation_module_imports()
    asyncio.run(test_create_invitation_basic())
    asyncio.run(test_non_manager_forbidden())
    
    print("\n✅ All simple tests passed!")