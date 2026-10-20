"""A separately deployed REST Auth Service; Gateway never opens the Auth DB."""
from contextlib import asynccontextmanager
import os

import psycopg
import redis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from back.lab3.common import DomainError
from .repository import AuthRepository
from .service import AuthFailure, AuthService, public_user


class Credentials(BaseModel):
    login: str
    password: str


class StaffPayload(BaseModel):
    login: str
    password: str
    roleCode: str
    idempotencyKey: str


class CommandKey(BaseModel):
    idempotencyKey: str


class RolePayload(CommandKey):
    roleCode: str


@asynccontextmanager
async def lifespan(app):
    repository = AuthRepository(os.environ["LAB5_AUTH_DSN"])
    app.state.security = AuthService(repository, os.environ["LAB5_REDIS_URL"],
                                      os.environ["LAB5_JWT_SECRET"],
                                      int(os.getenv("LAB5_SESSION_TTL", "1800")))
    yield


app = FastAPI(title="ЛР5 Auth Service", lifespan=lifespan)


@app.exception_handler(AuthFailure)
async def auth_error(_request, exc):
    return JSONResponse({"code": exc.code, "message": str(exc)}, status_code=exc.status)


@app.exception_handler(DomainError)
async def domain_error(_request, exc):
    return JSONResponse({"code": exc.code, "message": str(exc)},
                        status_code={"BAD_INPUT": 400, "NOT_FOUND": 404,
                                     "FORBIDDEN": 403, "CONFLICT": 409}.get(exc.code, 400))


@app.exception_handler(psycopg.errors.UniqueViolation)
async def duplicate(_request, _exc):
    return JSONResponse({"code": "CONFLICT", "message": "Логин уже существует"}, status_code=409)


@app.exception_handler(redis.RedisError)
async def redis_unavailable(_request, _exc):
    return JSONResponse({"code": "DEPENDENCY_UNAVAILABLE", "message": "Хранилище сессий недоступно"},
                        status_code=503)


@app.exception_handler(psycopg.OperationalError)
async def database_unavailable(_request, _exc):
    return JSONResponse({"code": "DEPENDENCY_UNAVAILABLE", "message": "База Auth недоступна"},
                        status_code=503)


def bearer(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthFailure("UNAUTHENTICATED", "Требуется Bearer JWT")
    token = authorization[7:].strip()
    if not token:
        raise AuthFailure("UNAUTHENTICATED", "Требуется Bearer JWT")
    return token


async def principal(request: Request, authorization: str | None):
    token = bearer(authorization)
    actor, _ = await run_in_threadpool(request.app.state.security.validate, token)
    return actor, token


@app.get("/health")
async def health(request: Request):
    try:
        database = await run_in_threadpool(request.app.state.security.repository.health)
        redis_ready = await run_in_threadpool(request.app.state.security.redis.ping)
        return {"service": "auth", "database": database["database"],
                "redisReady": bool(redis_ready), "sessionTtlSeconds": request.app.state.security.ttl,
                "ready": bool(redis_ready)}
    except (psycopg.Error, redis.RedisError, DomainError):
        return JSONResponse({"service": "auth", "ready": False}, status_code=503)


@app.post("/login")
async def login(values: Credentials, request: Request):
    return await run_in_threadpool(request.app.state.security.sign_in, values.login, values.password)


@app.get("/validate")
async def validate(request: Request, authorization: str | None = Header(default=None)):
    actor, _ = await principal(request, authorization)
    return public_user(actor)


@app.post("/logout")
async def logout(request: Request, authorization: str | None = Header(default=None)):
    _, token = await principal(request, authorization)
    return {"signedOut": await run_in_threadpool(request.app.state.security.sign_out, token)}


@app.post("/staff")
async def register_staff(values: StaffPayload, request: Request,
                         authorization: str | None = Header(default=None)):
    actor, _ = await principal(request, authorization)
    return await run_in_threadpool(request.app.state.security.register_staff, actor, values.model_dump())


@app.post("/staff/{user_id}/block")
async def block_staff(user_id: str, values: CommandKey, request: Request,
                      authorization: str | None = Header(default=None)):
    actor, _ = await principal(request, authorization)
    return await run_in_threadpool(request.app.state.security.block_staff,
                                   actor, user_id, values.idempotencyKey)


@app.post("/staff/{user_id}/role")
async def change_staff_role(user_id: str, values: RolePayload, request: Request,
                            authorization: str | None = Header(default=None)):
    actor, _ = await principal(request, authorization)
    return await run_in_threadpool(request.app.state.security.change_staff_role,
                                   actor, user_id, values.roleCode, values.idempotencyKey)
