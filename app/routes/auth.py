from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import create_access_token, get_current_user
from app.models.schemas import RegisterRequest, Token, User
from app.services import users

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    try:
        return users.create_user(request.username, request.password)
    except users.UsernameTaken:
        raise HTTPException(status_code=409, detail="That username is already taken.")


# Takes form fields (username, password) rather than JSON - that's the
# OAuth2 password-flow convention, and it makes the "Authorize" button
# in the /docs page work.
@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = users.authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Wrong username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user["id"]))


@router.get("/me", response_model=User)
def me(user: dict = Depends(get_current_user)):
    return user
