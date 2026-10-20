"""Protected GraphQL Gateway: trust only Auth Service's validated principal."""
from contextlib import asynccontextmanager
from datetime import datetime
import os

import strawberry
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from graphql import (GraphQLError, FieldNode, FragmentSpreadNode,
                     InlineFragmentNode, get_operation_ast, parse)
from starlette.concurrency import run_in_threadpool
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info

from back.lab3.common import DomainError
from back.lab3.graphql.dispatch import plain, hydrate
from back.lab3.graphql.types import AuthPayload, StaffInput, RoleCode, User
from back.lab4.graphql import Query, Mutation as BusinessMutation
from .auth_client import AuthAPIClient
from .bootstrap import build


QUERY_ROLES = {
    "ADMIN": {"me", "clients"},
    "MANAGER": {field.python_name for field in Query.__strawberry_definition__.fields},
    "ANALYST": {"me", "clients", "transactions", "transaction", "clientActivity",
                "profile", "analysisResult", "analysisRun", "ruleVersions",
                "reviewCases", "reviewCase", "notifications", "report", "exportReport"},
}
MUTATION_ROLES = {
    "ADMIN": {"signOut", "registerStaff", "blockStaff", "changeStaffRole",
              "createClient", "openAccount", "registerCounterparty"},
    "MANAGER": {"signOut", "createClient", "openAccount", "registerCounterparty",
                "registerTransaction", "reopenCase", "closeCase", "markNotificationRead"},
    "ANALYST": {"signOut", "registerTransaction", "takeCase", "addCaseComment", "escalateCase",
                "closeCase", "markNotificationRead"},
}


def auth_error(exc):
    raise GraphQLError(str(exc), extensions={"code": exc.code, "service": "auth"}) from None


@strawberry.type
class Mutation(BusinessMutation):
    @strawberry.mutation
    async def signIn(self, info: Info, *, login: str, password: str) -> AuthPayload:
        try:
            result = await run_in_threadpool(info.context["auth_api"].sign_in, login, password)
            result["expiresAt"] = datetime.fromisoformat(result["expiresAt"])
            return hydrate(AuthPayload, result)
        except DomainError as exc:
            auth_error(exc)

    @strawberry.mutation
    async def signOut(self, info: Info) -> bool:
        try:
            return await run_in_threadpool(info.context["auth_api"].sign_out,
                                           info.context["token"])
        except DomainError as exc:
            auth_error(exc)

    @strawberry.mutation
    async def registerStaff(self, info: Info, *, input: StaffInput) -> User:
        try:
            result = await run_in_threadpool(info.context["auth_api"].register_staff,
                                             info.context["token"], plain(input))
            return hydrate(User, result)
        except DomainError as exc:
            auth_error(exc)

    @strawberry.mutation
    async def blockStaff(self, info: Info, *, userId: strawberry.ID,
                         idempotencyKey: str) -> User:
        try:
            result = await run_in_threadpool(info.context["auth_api"].block_staff,
                                             info.context["token"], str(userId), idempotencyKey)
            return hydrate(User, result)
        except DomainError as exc:
            auth_error(exc)

    @strawberry.mutation
    async def changeStaffRole(self, info: Info, *, userId: strawberry.ID,
                              roleCode: RoleCode, idempotencyKey: str) -> User:
        try:
            result = await run_in_threadpool(info.context["auth_api"].change_staff_role,
                                             info.context["token"], str(userId),
                                             roleCode.value, idempotencyKey)
            return hydrate(User, result)
        except DomainError as exc:
            auth_error(exc)


schema = strawberry.Schema(query=Query, mutation=Mutation,
                           config=StrawberryConfig(auto_camel_case=False))


def root_fields(document, operation):
    fragments = {definition.name.value: definition for definition in document.definitions
                 if getattr(definition, "kind", None) == "fragment_definition"}
    fields = set()
    seen = set()

    def walk(selection_set):
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                fields.add(selection.name.value)
            elif isinstance(selection, InlineFragmentNode):
                walk(selection.selection_set)
            elif isinstance(selection, FragmentSpreadNode):
                name = selection.name.value
                if name in seen:
                    continue
                seen.add(name)
                if name in fragments:
                    walk(fragments[name].selection_set)

    walk(operation.selection_set)
    return fields


@asynccontextmanager
async def lifespan(app):
    app.state.container = build()
    app.state.auth_api = AuthAPIClient(os.environ["LAB5_AUTH_URL"])
    yield


app = FastAPI(title="ЛР5 — защищённый GraphQL", lifespan=lifespan)


async def context(request: Request):
    # GET /graphql without a query serves only the GraphiQL editor; requests
    # that execute an operation are authorized below before any resolver runs.
    if request.method == "GET" and "query" not in request.query_params:
        return {"request": request, "auth_api": request.app.state.auth_api}
    try:
        body = await request.json() if request.method == "POST" else request.query_params
        document = parse(body.get("query", ""))
        operation = get_operation_ast(document, body.get("operationName"))
        if operation is None:
            raise ValueError("Не выбрана GraphQL-операция")
        names = root_fields(document, operation)
        operation_type = operation.operation.value
    except (GraphQLError, ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail={"code": "BAD_INPUT",
                                                     "message": "Некорректный GraphQL-запрос"}) from None
    if operation_type == "mutation" and names == {"signIn"}:
        return {"request": request, "auth_api": request.app.state.auth_api}

    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED",
                                                     "message": "Требуется Bearer JWT"})
    token = authorization[7:].strip()
    try:
        verified = await run_in_threadpool(request.app.state.auth_api.validate, token)
    except DomainError as exc:
        status = 503 if exc.code == "DEPENDENCY_UNAVAILABLE" else 401
        raise HTTPException(status_code=status,
                            detail={"code": exc.code, "message": str(exc)}) from None
    allowed = QUERY_ROLES.get(verified["role"], set()) if operation_type == "query" else MUTATION_ROLES.get(verified["role"], set())
    if operation_type == "query":
        allowed = allowed | {"__schema", "__type", "__typename"}
    if not names or not names <= allowed:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN",
                                                     "message": "Нет прав на запрошенные поля GraphQL"})
    return {"request": request, "auth_api": request.app.state.auth_api,
            "token": token, "actor": verified,
            "clients": request.app.state.container.clients(verified)}


app.include_router(GraphQLRouter(schema, context_getter=context), prefix="/graphql")


@app.get("/schema.graphql", response_class=PlainTextResponse)
def sdl():
    return schema.as_str()


@app.get("/health")
async def health(request: Request):
    services = []
    for name, db in request.app.state.container.databases.items():
        try:
            services.append({"service": name, "status": "READY",
                             **await run_in_threadpool(db.health)})
        except DomainError:
            services.append({"service": name, "status": "UNAVAILABLE"})
    try:
        auth = await run_in_threadpool(request.app.state.auth_api.request, "GET", "/health")
        auth_ready = auth["ready"] and auth["redisReady"]
    except (DomainError, KeyError):
        auth = {"ready": False}
        auth_ready = False
    ready = auth_ready and all(row["status"] == "READY" for row in services)
    return JSONResponse({"stage": "LR5", "auth": auth, "services": services,
                         "queryCount": len(schema.get_type_by_name("Query").fields),
                         "mutationCount": len(schema.get_type_by_name("Mutation").fields),
                         "transport": "business-mock-in-process; auth-rest",
                         "allReady": ready}, status_code=200 if ready else 503)
