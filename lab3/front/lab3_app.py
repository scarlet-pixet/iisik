"""A real read-only UI for LR3, using GraphQL exclusively."""
import os,json
from pathlib import Path
import requests
import streamlit as st
URL=os.getenv('LAB3_GRAPHQL_URL','http://127.0.0.1:18003/graphql')
IDS=json.loads((Path(__file__).resolve().parents[1]/'docs/lab3/demo_ids.json').read_text())
st.set_page_config(page_title='ЛР3 — чтение банковских данных',layout='wide')
st.title('Анализ банковских операций — ЛР3')
def query(q,v=None):
    try:
        result=requests.post(URL,json={'query':q,'variables':v or {}},timeout=15).json()
        if result.get('errors'):st.error(result['errors']);st.stop()
        return result['data']
    except requests.RequestException:st.error('GraphQL API недоступен. Проверьте запуск Compose.');st.stop()
tab=st.sidebar.radio('Раздел',['Клиенты и счета','Обзор клиента','Карточка случая','Сравнение запусков'])
if st.sidebar.button('Обновить'):st.rerun()
if tab=='Клиенты и счета':
    data=query('{me{login role} clients{totalCount items{id displayName externalId accounts{externalId currency status}}}}')
    st.write('Пользователь:',data['me']);st.metric('Клиентов',data['clients']['totalCount'])
    for item in data['clients']['items']:
        st.subheader(item['displayName']);st.dataframe(item['accounts'],width='stretch')
elif tab=='Обзор клиента':
    data=query('query($c:ID!,$r:ID!){clientActivity(clientId:$c,runId:$r,currency:"BYN",period:{from:"2026-09-01T00:00:00Z",to:"2026-10-01T00:00:00Z"}){client{displayName} transactions{id amount currency occurredAt} profiles{sampleSize medianAmount madAmount} scoreDistribution partialErrors}}',{'c':IDS['client'],'r':IDS['run2']})['clientActivity']
    st.subheader(data['client']['displayName']);st.write('Распределение оценок:',data['scoreDistribution']);st.write('Профили:',data['profiles']);st.dataframe(data['transactions'],width='stretch')
elif tab=='Карточка случая':
    case=query('query($id:ID!){reviewCase(id:$id){id transactionId latestResultId status priority latestScore comments{text} decisions{outcome reason}}}',{'id':IDS['case']})['reviewCase']
    st.metric('Оценка',case['latestScore']);st.write('Статус:',case['status'],'Приоритет:',case['priority'])
    result=query('query($id:ID!){analysisResult(id:$id){score threshold hits{ruleCode contribution featureValue limitValue}}}',{'id':case['latestResultId']})['analysisResult']
    st.dataframe(result['hits'],width='stretch');st.write('Комментарии:',case['comments']);st.write('Решения:',case['decisions'])
else:
    result=query('query($a:ID!,$b:ID!){compareRuns(firstId:$a,secondId:$b){commonCount onlyFirstCount onlySecondCount changedScores newHits}}',{'a':IDS['run1'],'b':IDS['run2']})['compareRuns']
    cols=st.columns(3)
    for col,(label,key) in zip(cols,[('Общие операции','commonCount'),('Только первый','onlyFirstCount'),('Только второй','onlySecondCount')]):col.metric(label,result[key])
    st.subheader('Изменение баллов');st.dataframe(result['changedScores'],width='stretch');st.write('Новые срабатывания:',result['newHits'])
