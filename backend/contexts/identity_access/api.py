from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import asyncpg
import os

from contexts.identity_access.invitations import send_invite

router = APIRouter()
security = HTTPBearer()

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
        key = os.getenv("DATABASE_SECRET", "")
        _supabase_client = create_client(url, key)
    return _supabase_client


class InvitationRequest(BaseModel):
    email: str
    org_id: str
    project_id: str
    role: str
    discipline_scope_id: str


async def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    from fastapi import HTTPException
    try:
        supabase = _get_supabase()
        user = supabase.auth.get_user(credentials.credentials)
        return user.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")


@router.post("/invites")
async def create_invitation(
    request: InvitationRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    current_user = await _get_current_user(credentials)

    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    try:
        result = await send_invite(
            email=request.email,
            org_id=request.org_id,
            project_id=request.project_id,
            role=request.role,
            discipline_scope_id=request.discipline_scope_id,
            invited_by=current_user.id,
            supabase_client=_get_supabase(),
            connection=conn,
        )
        return result
    finally:
        await conn.close()
