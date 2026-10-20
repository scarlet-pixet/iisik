"""Integration tests against the isolated LR4 Docker stand."""
from decimal import Decimal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os

import pytest
import requests
import psycopg
from graphql import build_schema


URL=os.getenv('LAB4_GRAPHQL_URL','http://127.0.0.1:18004/graphql')
CASE_ID='2b0b0c86-05a6-5c61-b2f0-05928e914b38'


def key():return uuid4().hex


def gql(query,variables=None,role='manager'):
    response=requests.post(URL,json={'query':query,'variables':variables or {}},
                           headers={'X-Demo-Actor':role},timeout=20)
    response.raise_for_status()
    return response.json()


def result(query,variables=None,role='manager'):
    body=gql(query,variables,role)
    assert 'errors' not in body,body
    return body['data']


def error_code(query,variables=None,role='manager'):
    body=gql(query,variables,role)
    assert body.get('errors'),body
    return body['errors'][0].get('extensions',{}).get('code')


def test_health_and_contract():
    health=requests.get('http://127.0.0.1:18004/health',timeout=20).json()
    assert health['allReady'] and len(health['services'])==4
    assert health['transport']=='mock-in-process'
    assert not health['grpcLoaded'] and not health['kafkaLoaded']
    schema=build_schema(requests.get('http://127.0.0.1:18004/schema.graphql',timeout=20).text)
    assert len(schema.query_type.fields)==16 and len(schema.mutation_type.fields)==10
    assert 'transactionSummary' in schema.query_type.fields
    assert {'createClient','registerTransaction','takeCase','closeCase'} <= set(schema.mutation_type.fields)
    prior=build_schema((Path(__file__).resolve().parents[2]/'back/contracts/schema.graphql').read_text(encoding='utf-8'))
    for root, names in ((schema.query_type,prior.query_type.fields),
                        (schema.mutation_type,schema.mutation_type.fields)):
        for name in names:
            original=(prior.query_type if root is schema.query_type else prior.mutation_type).fields[name]
            current=root.fields[name]
            assert str(current.type)==str(original.type),name
            assert {k:str(v.type) for k,v in current.args.items()}=={
                k:str(v.type) for k,v in original.args.items()},name


def test_transaction_business_operations():
    baseline=result('{transactionSummary{transactionCount totalAmount}}')['transactionSummary']
    client_input={'externalId':'L4-'+key(),'displayName':'Клиент лабораторной 4',
                  'segment':'RETAIL','idempotencyKey':key()}
    create='mutation($x:ClientInput!){createClient(input:$x){id externalId displayName accounts{id}}}'
    client=result(create,{'x':client_input})['createClient']
    assert result(create,{'x':client_input})['createClient']==client
    assert error_code(create,{'x':{**client_input,'displayName':'Иное имя'}})=='CONFLICT'
    assert error_code(create,{'x':{**client_input,'idempotencyKey':key()}},'analyst')=='FORBIDDEN'
    concurrent_input={'externalId':'L4-'+key(),'displayName':'Параллельный повтор','idempotencyKey':key()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts=list(pool.map(lambda _:result(create,{'x':concurrent_input})['createClient'],range(2)))
    assert attempts[0]==attempts[1]

    account_input={'clientId':client['id'],'externalId':'ACC-'+key(),'currency':'BYN','idempotencyKey':key()}
    account=result('mutation($x:AccountInput!){openAccount(input:$x){id clientId currency status}}',
                   {'x':account_input})['openAccount']
    assert account['status']=='OPEN' and account['clientId']==client['id']
    counterparty=result('mutation($x:CounterpartyInput!){registerCounterparty(input:$x){id externalId}}',
        {'x':{'externalId':'CP-'+key(),'displayName':'Учебный получатель','idempotencyKey':key()}})['registerCounterparty']

    tx_input={'source':'lab4_test','externalId':'TX-'+key(),'accountId':account['id'],
              'counterpartyId':counterparty['id'],'amount':'123.45','currency':'BYN',
              'direction':'OUT','occurredAt':'2026-10-17T12:00:00Z','idempotencyKey':key()}
    mutation='mutation($x:TransactionInput!){registerTransaction(input:$x){id amount currency clientId}}'
    assert error_code(mutation,{'x':{**tx_input,'amount':'-1'}})=='BAD_INPUT'
    assert error_code(mutation,{'x':{**tx_input,'currency':'USD'}})=='BAD_INPUT'
    tx=result(mutation,{'x':tx_input})['registerTransaction']
    assert tx['clientId']==client['id'] and tx['amount']=='123.45'
    assert result(mutation,{'x':tx_input})['registerTransaction']==tx
    assert error_code(mutation,{'x':{**tx_input,'amount':'125.00'}})=='CONFLICT'

    page=result('query($id:ID!){transactions(filter:{clientId:$id,currency:"BYN",amountFrom:100,amountTo:200},page:{limit:10,sortBy:"amount",sortDirection:"DESC"}){totalCount items{id amount}}}',
                {'id':client['id']})['transactions']
    assert page['totalCount']==1 and page['items'][0]['id']==tx['id']
    summary=result('query($id:ID!){transactionSummary(filter:{clientId:$id}){transactionCount totalAmount averageAmount incomingCount outgoingCount}}',
                   {'id':client['id']})['transactionSummary']
    assert summary=={'transactionCount':1,'totalAmount':'123.45','averageAmount':'123.45','incomingCount':0,'outgoingCount':1}
    after=result('{transactionSummary{transactionCount totalAmount}}')['transactionSummary']
    assert after['transactionCount']==baseline['transactionCount']+1
    assert Decimal(after['totalAmount'])==Decimal(baseline['totalAmount'])+Decimal('123.45')
    assert result(mutation, {'x': {**tx_input, 'externalId': 'ANALYST-'+key(), 'idempotencyKey': key()}}, 'analyst')['registerTransaction']['id']
    assert result(create, {'x': {'externalId':'ADMIN-'+key(), 'displayName':'Справочник администратора', 'idempotencyKey':key()}}, 'admin')['createClient']['id']
    assert error_code('query{transactionSummary(filter:{amountFrom:200,amountTo:100}){transactionCount}}')=='BAD_INPUT'


def test_case_lifecycle_and_notification():
    get_case='query($id:ID!){reviewCase(id:$id){id status rowVersion reviewCycle assigneeId comments{id} decisions{id}}}'
    case=result(get_case,{'id':CASE_ID},'analyst')['reviewCase']
    if case['status'] in ('NEW','ASSIGNED'):
        case=result('mutation($id:ID!,$v:Int!,$k:String!){takeCase(caseId:$id,expectedVersion:$v,idempotencyKey:$k){status rowVersion}}',
                    {'id':CASE_ID,'v':case['rowVersion'],'k':key()},'analyst')['takeCase']
    if case['status'] in ('IN_PROGRESS','ESCALATED'):
        case=result('mutation($x:CaseDecisionInput!){closeCase(input:$x){status rowVersion}}',
                    {'x':{'caseId':CASE_ID,'outcome':'EXPLAINED','reason':'Подготовка повторного теста',
                          'expectedVersion':case['rowVersion'],'idempotencyKey':key()}},'analyst')['closeCase']
    assert case['status']=='CLOSED'
    version=case['rowVersion']
    reopen='mutation($id:ID!,$v:Int!,$k:String!){reopenCase(caseId:$id,reason:"Проверить повторно",expectedVersion:$v,idempotencyKey:$k){status rowVersion reviewCycle}}'
    assert error_code(reopen,{'id':CASE_ID,'v':version,'k':key()},'analyst')=='FORBIDDEN'
    reopened=result(reopen,{'id':CASE_ID,'v':version,'k':key()},'manager')['reopenCase']
    assert reopened['status']=='NEW' and reopened['rowVersion']==version+1
    take='mutation($id:ID!,$v:Int!,$k:String!){takeCase(caseId:$id,expectedVersion:$v,idempotencyKey:$k){status rowVersion assigneeId}}'
    assert error_code(take,{'id':CASE_ID,'v':version,'k':key()},'analyst')=='CONFLICT'
    taken=result(take,{'id':CASE_ID,'v':reopened['rowVersion'],'k':key()},'analyst')['takeCase']
    assert taken['status']=='IN_PROGRESS'
    comment=result('mutation($x:CaseCommentInput!){addCaseComment(input:$x){status rowVersion comments{id}}}',
        {'x':{'caseId':CASE_ID,'text':'Проверены исходные операции','idempotencyKey':key()}},'analyst')['addCaseComment']
    escalated=result('mutation($id:ID!,$v:Int!,$k:String!){escalateCase(caseId:$id,reason:"Требуется проверка",expectedVersion:$v,idempotencyKey:$k){status priority rowVersion}}',
        {'id':CASE_ID,'v':comment['rowVersion'],'k':key()},'analyst')['escalateCase']
    assert escalated['status']=='ESCALATED' and escalated['priority']=='HIGH'
    closed=result('mutation($x:CaseDecisionInput!){closeCase(input:$x){status rowVersion decisions{id outcome}}}',
        {'x':{'caseId':CASE_ID,'outcome':'UNUSUAL_CONFIRMED','reason':'Учебное решение',
              'expectedVersion':escalated['rowVersion'],'idempotencyKey':key()}},'manager')['closeCase']
    assert closed['status']=='CLOSED' and closed['decisions'][-1]['outcome']=='UNUSUAL_CONFIRMED'
    assert error_code('mutation($x:CaseCommentInput!){addCaseComment(input:$x){id}}',
        {'x':{'caseId':CASE_ID,'text':'После решения','idempotencyKey':key()}},'analyst')=='CONFLICT'

    notification_id=str(uuid4())
    case_dsn=os.getenv('LAB4_CASE_DSN','postgresql://bank_case:lab4_owner_only@127.0.0.1:57434/bank_case')
    with psycopg.connect(case_dsn) as conn:
        conn.execute(
            'INSERT INTO notifications(id,case_id,recipient_id,type,source_event_id,created_at) '
            'VALUES (%s,%s,%s,%s,%s,now())',
            (notification_id,CASE_ID,'43817961-b437-5313-9754-19535c80b1b9','CASE_UPDATED',str(uuid4())),
        )
    assert any(item['id']==notification_id for item in
        result('{notifications(unreadOnly:true,page:{limit:100,sortBy:"createdAt",sortDirection:"DESC"}){items{id}}}')['notifications']['items'])
    updated=result('mutation($id:ID!){markNotificationRead(id:$id){id readAt}}',
                   {'id':notification_id})['markNotificationRead']
    assert updated['readAt']
    assert result('mutation($id:ID!){markNotificationRead(id:$id){id readAt}}',
                  {'id':notification_id})['markNotificationRead']==updated
    assert error_code('mutation($id:ID!){markNotificationRead(id:$id){id}}',
                      {'id':notification_id},'analyst')=='NOT_FOUND'
    with psycopg.connect(case_dsn) as conn:
        assert conn.execute('SELECT read_at IS NOT NULL FROM notifications WHERE id=%s',
                            (notification_id,)).fetchone()[0]
