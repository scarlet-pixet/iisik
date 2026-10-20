from contextlib import asynccontextmanager
import logging,sys
from fastapi import FastAPI,Request
from fastapi.responses import PlainTextResponse,JSONResponse
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from starlette.concurrency import run_in_threadpool
import strawberry
from back.lab3.bootstrap import build
from back.lab3.common import DomainError
from .types import Query

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
schema=strawberry.Schema(query=Query,config=StrawberryConfig(auto_camel_case=False))

@asynccontextmanager
async def lifespan(app):
    app.state.container=build()
    yield

app=FastAPI(title='ЛР3 — Query API и mock-взаимодействие',lifespan=lifespan)
async def context(request:Request):return {'request':request,'clients':request.app.state.container.clients}
app.include_router(GraphQLRouter(schema,context_getter=context),prefix='/graphql')

@app.get('/schema.graphql',response_class=PlainTextResponse)
def sdl():return schema.as_str()

@app.get('/health')
async def health(request:Request):
    services=[]
    for name,db in request.app.state.container.databases.items():
        try:services.append({'service':name,'status':'READY',**await run_in_threadpool(db.health)})
        except DomainError:services.append({'service':name,'status':'UNAVAILABLE'})
    ready=all(x['status']=='READY' for x in services)
    return JSONResponse({'stage':'LR3','transport':'mock-in-process','authentication':'fixed demo identity; not authentication','queryCount':15,'mutationEnabled':False,'grpcLoaded':'grpc' in sys.modules,'kafkaLoaded':'confluent_kafka' in sys.modules,'services':services,'allReady':ready},status_code=200 if ready else 503)
