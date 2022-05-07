from turtle import st
from odmantic import Field, Model, Reference
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine,query
from typing import List, Optional, Any
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel
from bson import ObjectId
import os


MONGODB_URL = os.environ.get("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL)
engine = AIOEngine(motor_client=client, database="intellisite")
pwd_context = CryptContext(
        schemes=["pbkdf2_sha256"],
        default="pbkdf2_sha256",
        pbkdf2_sha256__default_rounds=30000
)

def encrypt_password(password):
    return pwd_context.encrypt(password)


def check_encrypted_password(password, hashed):
    return pwd_context.verify(password, hashed)


class User(Model):
    username: str
    password: Optional[str]

    async def save(self):
        self.password = encrypt_password(self.password)
        await engine.save(self)

    @classmethod
    async def authenticate(cls, user: str, password: str) -> 'User':
        user = await engine.find_one(User, User.username == user)
        if user:
            if check_encrypted_password(password, user.password):
                return user
    
    @classmethod
    async def get(cls, idx: str=None, username: str = None) -> 'User':
        if idx:
            user = await engine.find_one(User, User.id == ObjectId(idx))
        elif username:
            user = await engine.find_one(User, User.username == username)
        return user

    @classmethod
    async def all(cls) -> list:
        users = []
        async for i in engine.find(User,):
            users.append(i)
        return users
    
    async def delete(self):
        await engine.delete(self)


class Vehicle(Model):
    year: int
    make: str
    model: str
    category: str
    created: Optional[datetime]

    async def save(self):
        if self.created is None:
            self.created = datetime.now()
        await engine.save(self)
    
    async def serialize(self):
        data = self.doc()
        data['_id'] = str(data['_id'])
        return data
        
    @classmethod
    async def raw_query(cls, mongodb_query: dict, sort: Any, skip: int = 0, limit: int = None) -> List:
        result = await engine.find(Vehicle, mongodb_query, sort=sort, skip=skip, limit=limit)
        return result

    @classmethod
    async def count_per(cls, group):
        pipelines = [
            {"$group" : {"_id": f"${group}", "count":{"$sum":1}}}
        ]
        collection = engine.get_collection(Vehicle)
        documents = await collection.aggregate(pipelines).to_list(length=None)
        return documents
    
    @classmethod
    async def count(cls):
        return await engine.count(Vehicle)