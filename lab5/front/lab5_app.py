"""Authenticated LR5 UI. It only talks to the GraphQL Gateway."""
from datetime import datetime, timezone
from uuid import uuid4
import os

import requests
import streamlit as st


URL = os.getenv("LAB5_GRAPHQL_URL", "http://127.0.0.1:18005/graphql")
title = os.getenv("LAB_TITLE", "ЛР5 — защищённый анализ транзакций")
st.set_page_config(page_title=title, layout="wide")
st.title(title)


def call(query, variables=None, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    try:
        response = requests.post(URL, json={"query": query, "variables": variables or {}},
                                 headers=headers, timeout=20)
        payload = response.json()
        if response.status_code >= 400:
            detail = payload.get("detail", payload)
            return {"errors": [{"message": detail.get("message", str(detail))}]}
        return payload
    except (requests.RequestException, ValueError) as exc:
        return {"errors": [{"message": str(exc)}]}


if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:
    st.info("Войдите в учётную запись. Роль определяется Auth Service, а не настройкой браузера.")
    with st.form("login"):
        login = st.text_input("Логин", value="manager")
        password = st.text_input("Пароль", type="password")
        submit = st.form_submit_button("Войти")
    if submit:
        result = call("mutation($login:String!,$password:String!){signIn(login:$login,password:$password){accessToken expiresAt user{id login role}}}",
                      {"login": login, "password": password})
        if result.get("errors"):
            st.error(result["errors"][0]["message"])
        else:
            st.session_state.token = result["data"]["signIn"]["accessToken"]
            st.rerun()
    st.stop()


token = st.session_state.token
identity = call("query{me{id login role isActive}}", token=token)
if identity.get("errors"):
    st.session_state.token = None
    st.error("Сессия завершилась. Выполните вход снова.")
    st.stop()
user = identity["data"]["me"]
st.caption(f"Сотрудник: {user['login']} · роль: {user['role']}")
if st.button("Выйти"):
    call("mutation{signOut}", token=token)
    st.session_state.token = None
    st.rerun()


def show(result):
    if result.get("errors"):
        st.error("\n".join(item.get("message", "Ошибка") for item in result["errors"]))
    else:
        st.json(result["data"])


if user["role"] == "MANAGER":
    overview, client_tab, transaction_tab, case_tab = st.tabs(
        ["Сводка", "Новый клиент", "Транзакция", "Случаи"])
    with overview:
        client_id = st.text_input("ID клиента для фильтра (необязательно)")
        if st.button("Получить сводку"):
            filters = {"clientId": client_id.strip()} if client_id.strip() else {}
            show(call("query($f:TransactionFilter){transactionSummary(filter:$f){transactionCount totalAmount averageAmount incomingCount outgoingCount}}",
                      {"f": filters}, token))
        if st.button("Показать операции"):
            filters = {"clientId": client_id.strip()} if client_id.strip() else {}
            show(call("query($f:TransactionFilter){transactions(filter:$f,page:{limit:20,sortBy:\"occurredAt\",sortDirection:\"DESC\"}){totalCount items{id externalId amount currency direction}}}",
                      {"f": filters}, token))
    with client_tab:
        external = st.text_input("Внешний ID клиента")
        display = st.text_input("Имя клиента")
        if st.button("Создать клиента"):
            show(call("mutation($x:ClientInput!){createClient(input:$x){id externalId displayName}}",
                      {"x": {"externalId": external, "displayName": display,
                             "idempotencyKey": str(uuid4())}}, token))
    with transaction_tab:
        account = st.text_input("ID счёта")
        external_tx = st.text_input("Внешний ID операции")
        amount = st.text_input("Сумма", "100.00")
        if st.button("Зарегистрировать операцию"):
            data = {"source": "streamlit-lab5", "externalId": external_tx,
                    "accountId": account, "amount": amount, "currency": "BYN",
                    "direction": "OUT", "occurredAt": datetime.now(timezone.utc).isoformat(),
                    "idempotencyKey": str(uuid4())}
            show(call("mutation($x:TransactionInput!){registerTransaction(input:$x){id externalId amount currency}}",
                      {"x": data}, token))
    with case_tab:
        if st.button("Показать случаи"):
            show(call("query{reviewCases(page:{limit:20}){totalCount items{id status assigneeId rowVersion}}}",
                      token=token))
elif user["role"] == "ANALYST":
    st.subheader("Доступные случаи")
    if st.button("Показать мою очередь"):
        show(call("query{reviewCases(page:{limit:20}){totalCount items{id status priority assigneeId rowVersion}}}",
                  token=token))
    case_id = st.text_input("ID случая")
    if st.button("Открыть карточку и объяснение"):
        card = call("query($id:ID!){reviewCase(id:$id){id transactionId latestResultId status latestScore assigneeId rowVersion comments{text} decisions{outcome reason}}}",
                    {"id": case_id}, token)
        show(card)
        value = card.get("data", {}).get("reviewCase")
        if value:
            show(call("query($tx:ID!,$result:ID!){transaction(id:$tx){id amount currency direction occurredAt} analysisResult(id:$result){id score threshold dataStatus hits{ruleCode contribution featureValue limitValue}}}",
                      {"tx": value["transactionId"], "result": value["latestResultId"]}, token))
    version = st.number_input("Текущая версия случая", min_value=1, value=1)
    if st.button("Взять в работу"):
        show(call("mutation($id:ID!,$v:Int!,$k:String!){takeCase(caseId:$id,expectedVersion:$v,idempotencyKey:$k){id status assigneeId rowVersion}}",
                  {"id": case_id, "v": version, "k": str(uuid4())}, token))
    with st.expander("Зарегистрировать транзакцию"):
        account = st.text_input("ID счёта", key="analyst_account")
        external_tx = st.text_input("Внешний ID операции", key="analyst_external")
        amount = st.text_input("Сумма", "100.00", key="analyst_amount")
        if st.button("Зарегистрировать операцию"):
            show(call("mutation($x:TransactionInput!){registerTransaction(input:$x){id externalId amount currency}}",
                      {"x": {"source": "streamlit-analyst", "externalId": external_tx,
                             "accountId": account, "amount": amount, "currency": "BYN",
                             "direction": "OUT", "occurredAt": datetime.now(timezone.utc).isoformat(),
                             "idempotencyKey": str(uuid4())}}, token))
else:
    st.subheader("Администрирование сотрудников")
    login = st.text_input("Логин нового сотрудника")
    password = st.text_input("Пароль нового сотрудника", type="password")
    role = st.selectbox("Роль", ("ANALYST", "MANAGER", "ADMIN"))
    if st.button("Зарегистрировать сотрудника"):
        show(call("mutation($x:StaffInput!){registerStaff(input:$x){id login role isActive}}",
                  {"x": {"login": login, "password": password, "roleCode": role,
                         "idempotencyKey": str(uuid4())}}, token))
    with st.expander("Справочники клиентов и счетов"):
        external = st.text_input("Внешний ID клиента")
        display = st.text_input("Имя клиента")
        if st.button("Создать клиента"):
            show(call("mutation($x:ClientInput!){createClient(input:$x){id externalId displayName}}",
                      {"x": {"externalId": external, "displayName": display,
                             "idempotencyKey": str(uuid4())}}, token))
        if st.button("Показать клиентов"):
            show(call("query{clients{totalCount items{id externalId displayName accounts{id currency}}}}", token=token))
        client_id = st.text_input("ID клиента")
        account_external = st.text_input("Внешний ID счёта")
        account_currency = st.text_input("Валюта счёта", "BYN")
        if st.button("Открыть счёт"):
            show(call("mutation($x:AccountInput!){openAccount(input:$x){id externalId currency status}}",
                      {"x": {"clientId": client_id, "externalId": account_external,
                             "currency": account_currency, "idempotencyKey": str(uuid4())}}, token))
        cp_external = st.text_input("Внешний ID контрагента")
        cp_name = st.text_input("Имя контрагента")
        if st.button("Зарегистрировать контрагента"):
            show(call("mutation($x:CounterpartyInput!){registerCounterparty(input:$x){id externalId}}",
                      {"x": {"externalId": cp_external, "displayName": cp_name,
                             "idempotencyKey": str(uuid4())}}, token))
