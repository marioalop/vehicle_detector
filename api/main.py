import os
from fastapi import FastAPI, HTTPException, Request, Depends, File, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mqmfork import mqmfork as mqm
from pydantic import BaseModel
from datetime import timedelta
from schemas import User, Vehicle
from typing import List


JWT_EXPIRE = timedelta(3600)
JWT_SECRET =  '45c86f7ab8044d499f6b8f632167f33f'


class Settings(BaseModel):
    authjwt_secret_key: str = JWT_SECRET
    authjwt_access_token_expires= JWT_EXPIRE


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@AuthJWT.load_config
def get_config():
    return Settings()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


@app.post('/login')
async def login(login_form: User, Authorize: AuthJWT = Depends()):
    user = await User.authenticate(login_form.username, login_form.password)
    if not user:
        raise HTTPException(status_code=401,detail="Bad username or password")

    if user.is_active is False:
        raise HTTPException(status_code=401, detail='User is not active')
    
    # subject identifier for who this token is for example id or username from database
    access_token = Authorize.create_access_token(subject=user.username, user_claims={"id": str(user.id)}, fresh=True)
    refresh_token = Authorize.create_refresh_token(subject=user.username, user_claims={"id": str(user.id)})

    return {"access_token": access_token, "refresh_token": refresh_token, "expire": JWT_EXPIRE}


@app.post('/refresh')
def refresh(Authorize: AuthJWT = Depends()):
    Authorize.jwt_refresh_token_required()
    current_user = Authorize.get_jwt_subject()
    new_access_token = Authorize.create_access_token(subject=current_user, user_claims={'id': str(current_user.id)},fresh=False)
    return {"access_token": new_access_token, "expire": JWT_EXPIRE}


@app.get('/users/create-superuser', response_description="Create superuser", response_model=User)
async def create_superuser():
    u = await User.get(username="admin")
    if not u:
        u = User(username = 'admin', password = 'Intellisite##789')
        await u.save()    
    return {}

@app.post('/users', response_description="Create user", response_model=User)
async def create_user(user: User, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    u = await User.get(username = user.username)
    if not u:
        u = User(username = user.username, password = user.password)
        await u.save()    
        return u
    raise HTTPException(status_code=401, detail=f"User {user.username} already exists.")

@app.post('/get', response_description="List detections", response_model=List[Vehicle])
async def detections(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    sort_opt = {
        "make": Vehicle.make,
        "-make": Vehicle.make.desc(),
        "year": Vehicle.year,
        "-year": Vehicle.year.desc(),
        "model": Vehicle.model,
        "-model": Vehicle.model.desc(),
        "category": Vehicle.category,
        "-category": Vehicle.category.desc(),
        "created": Vehicle.created,
        "-created": Vehicle.created.desc(),
    }
    ops = {
        "__gt=": ">",
        "__gte=": ">=",
        "__lt=": "<",
        "__lte=": "<="
    }
    for op in ops:
        params = params.replace(op, ops[op])
    params = str(request.query_params)
    params = mqm(string_query=params)
    sort = sort_opt[params.pop("sort")]
    data = await Vehicle.raw_query(params["filter"], sort, params["skip"], params["limit"])
    return data

