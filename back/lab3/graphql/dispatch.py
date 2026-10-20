"""GraphQL mapping only. No SQL, repository imports, or business calculations."""
import dataclasses,types,typing,re
from enum import Enum
from datetime import datetime
from decimal import Decimal
from graphql import GraphQLError
from starlette.concurrency import run_in_threadpool
import psycopg
from back.lab3.common import DomainError
from . import types as models

ROUTES={
 'me':('auth','get_current_user'), 'clients':('transaction','search_clients'),
 'transactions':('transaction','search_transactions'), 'transaction':('transaction','get_transaction'),
 'clientActivity':('analysis','get_client_activity'), 'profile':('analysis','get_profile'),
 'analysisResult':('analysis','get_result'), 'analysisRun':('analysis','get_run'),
 'compareRuns':('analysis','compare_runs'), 'ruleVersions':('analysis','list_rule_versions'),
 'reviewCases':('case','search_cases'), 'reviewCase':('case','get_case'),
 'report':('case','get_report'), 'exportReport':('case','export_report'), 'notifications':('case','list_notifications')}
OUTPUTS={'me':'User','clients':'ClientPage','transactions':'TransactionPage','transaction':'Transaction','clientActivity':'ClientActivity','profile':'BehaviorProfile','analysisResult':'AnalysisResult','analysisRun':'AnalysisRun','compareRuns':'RunComparison','ruleVersions':'RuleVersion','reviewCases':'CasePage','reviewCase':'ReviewCase','report':'Report','exportReport':'ReportExport','notifications':'NotificationPage'}

def plain(value,output=False):
    if dataclasses.is_dataclass(value):
        def key(name):
            name=name.removesuffix('_')
            return re.sub(r'_([a-z])',lambda m:m[1].upper(),name) if output else name
        return {key(f.name):plain(getattr(value,f.name),output) for f in dataclasses.fields(value) if output or getattr(value,f.name) is not None}
    if isinstance(value,dict):return {k:plain(v,output) for k,v in value.items() if output or v is not None}
    if isinstance(value,list):return [plain(x,output) for x in value]
    if isinstance(value,Enum):return value.value
    return value

def hydrate(typ,value):
    if value is None:return None
    origin=typing.get_origin(typ);args=typing.get_args(typ)
    if origin in (typing.Union,types.UnionType):return hydrate(next(t for t in args if t is not type(None)),value)
    if origin is list:return [hydrate(args[0],x) for x in value]
    if typ is datetime and isinstance(value,str):return datetime.fromisoformat(value.replace('Z','+00:00'))
    if typ is Decimal and isinstance(value,str):return Decimal(value)
    if isinstance(typ,type) and issubclass(typ,Enum):return typ(value)
    if dataclasses.is_dataclass(typ):
        hints=typing.get_type_hints(typ)
        return typ(**{f.name:hydrate(hints[f.name],value.get(f.name.removesuffix('_'))) for f in dataclasses.fields(typ)})
    return value

async def dispatch(field,info,arguments):
    owner,method=ROUTES[field]
    try:
        value=await run_in_threadpool(getattr(getattr(info.context['clients'],owner),method),**plain(arguments))
        typ=getattr(models,OUTPUTS[field]);typ=list[typ] if field=='ruleVersions' else typ
        return hydrate(typ,plain(value,True))
    except DomainError as exc:
        raise GraphQLError(str(exc),extensions={'code':exc.code,'service':owner}) from None
    except psycopg.Error:
        raise GraphQLError('Ошибка чтения данных',extensions={'code':'DATA_ACCESS_ERROR','service':owner}) from None
