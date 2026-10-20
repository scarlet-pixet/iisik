"""Credential checking, JWT and Redis session lifecycle belong to Auth Service."""
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from time import time
from uuid import uuid4
import os
import re

import jwt
import redis

from back.lab3.common import DomainError, uuid
from back.lab4.common import required_text


class AuthFailure(Exception):
    def __init__(self, code, message, status=401):
        self.code, self.status = code, status
        super().__init__(message)


def public_user(row):
    return {"id": row["id"], "login": row["login"],
            "role": row["role"], "isActive": row["is_active"]}


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100000 <= int(iterations) <= 2000000:
            return False
        actual = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, UnicodeError):
        return False


def hash_password(password):
    salt = os.urandom(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


class AuthService:
    def __init__(self, repository, redis_url, jwt_secret, ttl=1800):
        if len(jwt_secret) < 32:
            raise RuntimeError("LAB5_JWT_SECRET must contain at least 32 characters")
        self.repository = repository
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True,
                                          socket_connect_timeout=3, socket_timeout=3)
        self.secret = jwt_secret
        self.ttl = ttl

    @staticmethod
    def session_key(jti):
        return "lab5:session:" + jti

    def sign_in(self, login, password):
        if not isinstance(login, str) or not isinstance(password, str):
            raise AuthFailure("UNAUTHENTICATED", "Неверный логин или пароль")
        row = self.repository.by_login(login.strip().lower())
        if row is None or not row["is_active"] or not verify_password(password, row["password_hash"]):
            raise AuthFailure("UNAUTHENTICATED", "Неверный логин или пароль")
        issued = int(time())
        jti = uuid4().hex
        self.redis.setex(self.session_key(jti), self.ttl, row["id"])
        token = jwt.encode({"sub": row["id"], "jti": jti, "iat": issued,
                            "exp": issued + self.ttl, "iss": "bank-lab5-auth",
                            "aud": "bank-lab5-gateway"}, self.secret, algorithm="HS256")
        return {"accessToken": token,
                "expiresAt": datetime.fromtimestamp(issued + self.ttl, timezone.utc).isoformat(),
                "user": public_user(row)}

    def validate(self, token):
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"],
                                issuer="bank-lab5-auth", audience="bank-lab5-gateway",
                                options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]})
            subject = uuid(claims["sub"])
            jti = claims["jti"]
            if not isinstance(jti, str) or not re.fullmatch(r"[0-9a-f]{32}", jti):
                raise ValueError("Invalid session identifier")
        except (jwt.PyJWTError, DomainError, ValueError, TypeError):
            raise AuthFailure("UNAUTHENTICATED", "Недействительный или просроченный JWT") from None
        if self.redis.get(self.session_key(jti)) != subject:
            raise AuthFailure("UNAUTHENTICATED", "Сессия отсутствует или истекла")
        row = self.repository.by_id(subject)
        if row is None or not row["is_active"]:
            raise AuthFailure("UNAUTHENTICATED", "Учётная запись недоступна")
        return row, jti

    def sign_out(self, token):
        _, jti = self.validate(token)
        self.redis.delete(self.session_key(jti))
        return True

    @staticmethod
    def require_admin(actor):
        if actor["role"] != "ADMIN":
            raise AuthFailure("FORBIDDEN", "Операция доступна только администратору", 403)

    def register_staff(self, actor, values):
        self.require_admin(actor)
        login = required_text(values.get("login"), "login", 64).lower()
        if not re.fullmatch(r"[a-z0-9._-]{3,64}", login):
            raise DomainError("BAD_INPUT", "Логин: 3–64 латинских символа, цифры, точка, дефис или подчёркивание")
        password = values.get("password")
        if not isinstance(password, str) or not 10 <= len(password) <= 128:
            raise DomainError("BAD_INPUT", "Пароль: 10–128 символов")
        role = values.get("roleCode")
        if role not in ("ADMIN", "ANALYST", "MANAGER"):
            raise DomainError("BAD_INPUT", "Неизвестная роль")
        row = self.repository.register(actor, login, hash_password(password), role,
                                       values.get("idempotencyKey"), sha256(password.encode()).hexdigest())
        return public_user(row)

    def block_staff(self, actor, user_id, key):
        self.require_admin(actor)
        user_id = uuid(user_id)
        if user_id == actor["id"]:
            raise DomainError("CONFLICT", "Нельзя заблокировать собственную учётную запись")
        return public_user(self.repository.block(actor, user_id, key))

    def change_staff_role(self, actor, user_id, role, key):
        self.require_admin(actor)
        user_id = uuid(user_id)
        if user_id == actor["id"]:
            raise DomainError("CONFLICT", "Нельзя изменить собственную роль")
        if role not in ("ADMIN", "ANALYST", "MANAGER"):
            raise DomainError("BAD_INPUT", "Неизвестная роль")
        return public_user(self.repository.change_role(actor, user_id, role, key))
