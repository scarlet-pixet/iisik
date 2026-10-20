"""Small real UI for the LR4 GraphQL stage. All writes go through GraphQL."""
import json
import os
from uuid import uuid4

import requests
import streamlit as st

URL=os.getenv('LAB4_GRAPHQL_URL','http://127.0.0.1:18004/graphql')
st.set_page_config(page_title='ЛР4 — операции банка',layout='wide')
st.title('ЛР4 — анализ транзакций и рассмотрение случаев')
role=st.selectbox('Учебная роль',('manager','analyst','admin'))
st.caption('X-Demo-Actor выбирает учебную роль; это не производственная аутентификация.')


def call(query,variables=None):
    try:
        response=requests.post(URL,json={'query':query,'variables':variables or {}},
                               headers={'X-Demo-Actor':role},timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {'errors':[{'message':str(exc)}]}


def show(data):
    if data.get('errors'):
        st.error('\n'.join(item['message'] for item in data['errors']))
    else:
        st.json(data['data'])


tabs=st.tabs(['Сводка и поиск','Новый клиент','Транзакция','Случаи'])


with tabs[0]:
    client=st.text_input('ID клиента для фильтра (необязательно)')
    direction=st.selectbox('Направление',('любое','IN','OUT'))
    if st.button('Получить сводку'):
        filters={}
        if client.strip():filters['clientId']=client.strip()
        if direction!='любое':filters['direction']=direction
        show(call('query($f:TransactionFilter){transactionSummary(filter:$f){transactionCount totalAmount averageAmount minimumAmount maximumAmount incomingCount outgoingCount}}',{'f':filters}))
    if st.button('Показать операции'):
        show(call('query($f:TransactionFilter){transactions(filter:$f,page:{limit:20,sortBy:"occurredAt",sortDirection:"DESC"}){totalCount items{id externalId amount currency direction occurredAt}}}',{'f':{'clientId':client} if client.strip() else {}}))


with tabs[1]:
    external=st.text_input('Внешний ID клиента')
    display=st.text_input('Имя клиента')
    if st.button('Создать клиента'):
        show(call('mutation($x:ClientInput!){createClient(input:$x){id externalId displayName isActive}}',
                  {'x':{'externalId':external,'displayName':display,'idempotencyKey':str(uuid4())}}))


with tabs[2]:
    account=st.text_input('ID счёта')
    external_tx=st.text_input('Внешний ID операции')
    amount=st.text_input('Сумма','100.00')
    currency=st.text_input('Валюта','BYN')
    if st.button('Зарегистрировать операцию'):
        from datetime import datetime,timezone
        payload={'source':'streamlit','externalId':external_tx,'accountId':account,'amount':amount,
                 'currency':currency,'direction':'OUT','occurredAt':datetime.now(timezone.utc).isoformat(),
                 'idempotencyKey':str(uuid4())}
        show(call('mutation($x:TransactionInput!){registerTransaction(input:$x){id externalId amount currency occurredAt}}',{'x':payload}))


with tabs[3]:
    if st.button('Показать случаи'):
        show(call('query{reviewCases(page:{limit:20,sortBy:"createdAt",sortDirection:"DESC"}){totalCount items{id status priority assigneeId rowVersion reviewCycle}}}'))
    case_id=st.text_input('ID случая')
    version=st.number_input('Ожидаемая версия',min_value=1,value=3,step=1)
    reason=st.text_input('Причина повторного открытия','Повторная проверка учебного случая')
    if st.button('Открыть повторно'):
        show(call('mutation($id:ID!,$r:String!,$v:Int!,$k:String!){reopenCase(caseId:$id,reason:$r,expectedVersion:$v,idempotencyKey:$k){id status rowVersion reviewCycle}}',
                  {'id':case_id,'r':reason,'v':version,'k':str(uuid4())}))
    if st.button('Взять в работу'):
        show(call('mutation($id:ID!,$v:Int!,$k:String!){takeCase(caseId:$id,expectedVersion:$v,idempotencyKey:$k){id status assigneeId rowVersion}}',
                  {'id':case_id,'v':version,'k':str(uuid4())}))
