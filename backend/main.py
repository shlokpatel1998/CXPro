from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging
import traceback
import os
from dotenv import load_dotenv
from db import get_supabase_client, get_db_connection
from auth import security, get_current_user
from invitation_service import InvitationService

load_dotenv()

app = FastAPI(title="CXPro Backend", version="0.1.0")

# CORS: allow the frontend dev server (and FRONTEND_URL in deployed envs) to call POST /invites etc.
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("cxpro.backend")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Convert every unhandled exception into a JSON 500. Returning a Response
    from the handler (instead of letting the exception propagate) lets
    CORSMiddleware decorate it with Access-Control-Allow-Origin, so the
    browser surfaces the real error instead of a misleading CORS failure.
    """
    logger.error(
        "Unhandled %s on %s %s:\n%s",
        type(exc).__name__,
        request.method,
        request.url.path,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )

class InvitationRequest(BaseModel):
    """Request model for creating an invitation"""
    email: str
    org_id: str
    project_id: str
    role: str
    discipline_scope_id: str


@app.post("/invites")
async def create_invitation(
    request: InvitationRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    response: Response = None
):
    """
    Create a new invitation and send magic link email
    
    Requires:
    - Caller must be OCA of the target organization
    - Valid JWT token in Authorization header
    
    Returns:
    - 201 for new invitations (CreateNew or ReplaceExpired)
    - 200 for resends (IncrementResend)
    - 409 for cap reached, self-invite, or already-member
    - 403 for non-OCA attempts
    """
    current_user = await get_current_user(credentials)

    supabase = get_supabase_client()
    conn = await get_db_connection()

    try:
        service = InvitationService(supabase, conn)
        
        result, status_code = await service.create_invitation(
            email=request.email,
            org_id=request.org_id,
            project_id=request.project_id,
            role=request.role,
            discipline_scope_id=request.discipline_scope_id,
            invited_by=current_user.id
        )

        response.status_code = status_code

        return result
    
    finally:
        await conn.close()


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "ok"}


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "CXPro Backend API", "version": "0.1.0"}