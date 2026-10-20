"""External GraphQL boundary: validation and state changes live in services."""
from contextlib import asynccontextmanager
import sys
from decimal import Decimal

import psycopg
import strawberry
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from graphql import GraphQLError
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info
from starlette.concurrency import run_in_threadpool

from back.lab3.common import DomainError
from back.lab3.graphql.dispatch import plain, hydrate
from back.lab3.graphql.types import (
    Query as ReadQuery, Client, Account, Counterparty, Transaction,
    ReviewCase, Notification, ClientInput, AccountInput, CounterpartyInput,
    TransactionInput, CaseCommentInput, CaseDecisionInput, TransactionFilter,
)
from back.lab4.bootstrap import build, ACTORS


@strawberry.type
class TransactionSummaryResult:
    transactionCount:int
    totalAmount:Decimal
    averageAmount:Decimal | None
    minimumAmount:Decimal | None
    maximumAmount:Decimal | None
    incomingCount:int
    outgoingCount:int


async def invoke(owner, method, typ, info, args):
    try:
        clients = info.context['clients']
        actor = await run_in_threadpool(clients.auth.get_current_user)
        value = await run_in_threadpool(getattr(getattr(clients,owner),method),actor=actor,**plain(args))
        return hydrate(typ,plain(value,True))
    except DomainError as exc:
        raise GraphQLError(str(exc),extensions={'code':exc.code,'service':owner}) from None
    except psycopg.errors.UniqueViolation:
        raise GraphQLError('Объект с таким внешним идентификатором уже существует',
                           extensions={'code':'CONFLICT','service':owner}) from None
    except psycopg.Error:
        raise GraphQLError('Ошибка хранения данных',extensions={'code':'DATA_ACCESS_ERROR','service':owner}) from None


@strawberry.type
class Query(ReadQuery):
    @strawberry.field
    async def transactionSummary(self, info:Info, *, filter:TransactionFilter | None = None) -> TransactionSummaryResult:
        try:
            value = await run_in_threadpool(info.context['clients'].transaction.transaction_summary,filter=plain(filter))
            return hydrate(TransactionSummaryResult,value)
        except DomainError as exc:
            raise GraphQLError(str(exc),extensions={'code':exc.code,'service':'transaction'}) from None


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def createClient(self, info:Info, *, input:ClientInput) -> Client:
        return await invoke('transaction','create_client',Client,info,{'input':input})

    @strawberry.mutation
    async def openAccount(self, info:Info, *, input:AccountInput) -> Account:
        return await invoke('transaction','open_account',Account,info,{'input':input})

    @strawberry.mutation
    async def registerCounterparty(self, info:Info, *, input:CounterpartyInput) -> Counterparty:
        return await invoke('transaction','register_counterparty',Counterparty,info,{'input':input})

    @strawberry.mutation
    async def registerTransaction(self, info:Info, *, input:TransactionInput) -> Transaction:
        return await invoke('transaction','register_transaction',Transaction,info,{'input':input})

    @strawberry.mutation
    async def takeCase(self, info:Info, *, caseId:strawberry.ID, expectedVersion:int, idempotencyKey:str) -> ReviewCase:
        return await invoke('case','take_case',ReviewCase,info,{'caseId':caseId,'expectedVersion':expectedVersion,'idempotencyKey':idempotencyKey})

    @strawberry.mutation
    async def addCaseComment(self, info:Info, *, input:CaseCommentInput) -> ReviewCase:
        return await invoke('case','add_case_comment',ReviewCase,info,{'input':input})

    @strawberry.mutation
    async def escalateCase(self, info:Info, *, caseId:strawberry.ID, reason:str, expectedVersion:int, idempotencyKey:str) -> ReviewCase:
        return await invoke('case','escalate_case',ReviewCase,info,{'caseId':caseId,'reason':reason,'expectedVersion':expectedVersion,'idempotencyKey':idempotencyKey})

    @strawberry.mutation
    async def closeCase(self, info:Info, *, input:CaseDecisionInput) -> ReviewCase:
        return await invoke('case','close_case',ReviewCase,info,{'input':input})

    @strawberry.mutation
    async def reopenCase(self, info:Info, *, caseId:strawberry.ID, reason:str, expectedVersion:int, idempotencyKey:str) -> ReviewCase:
        return await invoke('case','reopen_case',ReviewCase,info,{'caseId':caseId,'reason':reason,'expectedVersion':expectedVersion,'idempotencyKey':idempotencyKey})

    @strawberry.mutation
    async def markNotificationRead(self, info:Info, *, id:strawberry.ID) -> Notification:
        return await invoke('case','mark_notification_read',Notification,info,{'id':id})


schema = strawberry.Schema(query=Query,mutation=Mutation,config=StrawberryConfig(auto_camel_case=False))


@asynccontextmanager
async def lifespan(app):
    app.state.container=build()
    yield


app=FastAPI(title='ЛР4 — бизнес-операции и GraphQL',lifespan=lifespan)


async def context(request:Request):
    actor_name=request.headers.get('X-Demo-Actor','manager').lower()
    if actor_name not in ACTORS:
        raise HTTPException(status_code=400,detail='Неизвестная учебная роль')
    return {'request':request,'clients':request.app.state.container.clients(actor_name)}


app.include_router(GraphQLRouter(schema,context_getter=context),prefix='/graphql')


@app.get('/schema.graphql',response_class=PlainTextResponse)
def sdl():return schema.as_str()


@app.get('/health')
async def health(request:Request):
    services=[]
    for name,db in request.app.state.container.databases.items():
        try:services.append({'service':name,'status':'READY',**await run_in_threadpool(db.health)})
        except DomainError:services.append({'service':name,'status':'UNAVAILABLE'})
    ready=all(row['status']=='READY' for row in services)
    return JSONResponse({'stage':'LR4','transport':'mock-in-process','authentication':'X-Demo-Actor is a local teaching selector, not authentication',
                         'queryCount':16,'mutationCount':10,'grpcLoaded':'grpc' in sys.modules,
                         'kafkaLoaded':'confluent_kafka' in sys.modules,'services':services,'allReady':ready},
                        status_code=200 if ready else 503)
