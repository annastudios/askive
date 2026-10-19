from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import create_access_token, get_current_user
from app.models.schemas import RegisterRequest, Token, User
from app.services import users

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    try:
        return users.create_user(request.email, request.password)
    except users.EmailTaken:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")


# Takes form fields (username, password) rather than JSON - that's the
# OAuth2 password-flow convention, and it makes the "Authorize" button
# in the /docs page work. The spec names the field "username"; Askive
# puts the email address in it.
@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = users.authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Wrong email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user["id"]))


@router.get("/me", response_model=User)
def me(user: dict = Depends(get_current_user)):
    return user
