"""
Authentication endpoints — register, login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import User, UserRole
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.

    The first account ever registered is automatically promoted to admin.
    All subsequent accounts are plain users.
    """
    # Uniqueness checks
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    is_first = db.query(User).count() == 0
    user = User(
        username=body.username,
        email=str(body.email),
        hashed_password=hash_password(body.password),
        role=UserRole.admin if is_first else UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Exchange credentials for a JWT access token.

    The token is valid for 24 hours and must be sent as a Bearer token
    on all protected endpoints.
    """
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": user.username, "role": user.role.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), token: str = ""):
    """Return the currently authenticated user's profile."""
    # Handled via Depends in the dependency chain — import here to avoid circular
    from ..auth import get_current_user
    from fastapi import Request

    # Re-export for clients — actual auth is via Depends
    raise HTTPException(status_code=501, detail="Use Bearer token auth")
