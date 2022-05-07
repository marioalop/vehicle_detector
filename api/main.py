import os
from fastapi import FastAPI, HTTPException, Request, Depends, File, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from mqmfork import mqmfork as mqm
from pydantic import BaseModel
from datetime import timedelta
from schemas import User, Vehicle
from typing import List, Dict
import asyncio
from aiokafka import AIOKafkaConsumer
import json


JWT_EXPIRE = timedelta(3600)
JWT_SECRET =  '45c86f7ab8044d499f6b8f632167f33f'
KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL")
ALERTS_TOPIC = os.environ.get("ALERTS_TOPIC")

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


@app.get('/users/create-superuser', response_description="Create superuser")
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


@app.get('/detections', response_description="List detections")
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
    params = str(request.query_params)
    for op in ops:
        params = params.replace(op, ops[op])
    params = mqm(string_query=params)
    params['limit'] = 100 if params['limit'] == 0 else params['limit']
    sort = params.pop("sort", '-created')
    sort = sort_opt['-created']  if sort is None else sort_opt[sort]
    data = await Vehicle.raw_query(params["filter"], sort, params["skip"], params["limit"])
    return {"skip": params["skip"], "limit": params["limit"], "total": await Vehicle.count(params["filter"]), "data": data}


@app.get("/stats", response_description="Vehicle counting per Make")
async def stats(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    data = await Vehicle.count_per("make")
    return data


@app.get('/alerts')
async def message_stream(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    async def consume():
        consumer = AIOKafkaConsumer(ALERTS_TOPIC, bootstrap_servers=KAFKA_BROKER_URL)
        await consumer.start()
        try:
            async for msg in consumer:
                yield msg.value.decode()
        finally:
            await consumer.stop()
    return EventSourceResponse(consume())
