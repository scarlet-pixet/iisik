"""Live LR5 integration tests against Auth Service, Redis, Gateway and DBs."""
from pathlib import Path
from time import sleep, time
from uuid import uuid4
import os

import jwt
import psycopg
import pytest
import redis
import requests
from graphql import build_schema


ROOT = Path(__file__).resolve().parents[2]
URL = os.getenv("LAB5_GRAPHQL_URL", "http://127.0.0.1:18005/graphql")
AUTH = os.getenv("LAB5_AUTH_URL", "http://127.0.0.1:18015")
PASSWORD = "Lab2-demo-2026!"
CASE_ID = "2b0b0c86-05a6-5c61-b2f0-05928e914b38"


def settings():
    result = {}
    for line in (ROOT / ".env.lab5").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            result[name] = value
    return result


def gql(query, variables=None, token=None, extra_headers=None):
    headers = dict(extra_headers or {})
    if token:
        headers["Authorization"] = "Bearer " + token
    response = requests.post(URL, json={"query": query, "variables": variables or {}},
                             headers=headers, timeout=20)
    return response.status_code, response.json()


def data(query, variables=None, token=None, extra_headers=None):
    status, result = gql(query, variables, token, extra_headers)
    assert status == 200 and "errors" not in result, (status, result)
    return result["data"]


def login(name, password=PASSWORD):
    payload = data("mutation($n:String!,$p:String!){signIn(login:$n,password:$p){accessToken expiresAt user{id login role}}}",
                   {"n": name, "p": password})["signIn"]
    return payload["accessToken"]


def test_health_and_schema_preserve_previous_work():
    health = requests.get(URL.replace("/graphql", "/health"), timeout=20).json()
    assert health["allReady"] and health["auth"]["redisReady"]
    assert health["auth"]["database"] == "bank_auth"
    assert health["queryCount"] == 16 and health["mutationCount"] == 15
    assert health["transport"] == "business-mock-in-process; auth-rest"
    schema = build_schema(requests.get(URL.replace("/graphql", "/schema.graphql"), timeout=20).text)
    prior = build_schema((ROOT / "back/contracts/schema.graphql").read_text(encoding="utf-8"))
    assert len(schema.query_type.fields) == 16
    assert set(prior.query_type.fields) <= set(schema.query_type.fields)
    for name in prior.query_type.fields:
        expected, actual = prior.query_type.fields[name], schema.query_type.fields[name]
        assert str(expected.type) == str(actual.type)
        assert {key: str(value.type) for key, value in expected.args.items()} == {
            key: str(value.type) for key, value in actual.args.items()}
    for name in schema.mutation_type.fields:
        expected, actual = prior.mutation_type.fields[name], schema.mutation_type.fields[name]
        assert str(expected.type) == str(actual.type)
        assert {key: str(value.type) for key, value in expected.args.items()} == {
            key: str(value.type) for key, value in actual.args.items()}


def test_login_jwt_session_logout_and_spoofed_header():
    assert gql("query{me{login}}")[0] == 401
    assert gql("query{clients{totalCount}}")[0] == 401
    assert gql("mutation{signIn(login:\"manager\",password:\"wrong-password\"){accessToken}}")[1]["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
    assert gql("mutation{signIn(login:\"manager\",password:\"x\"){accessToken} signOut}")[0] == 401
    token = login("manager")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] and claims["jti"] and claims["exp"] > time()
    conf = settings()
    header, payload, signature = token.split(".")
    forged = ".".join((header, payload, ("A" if signature[0] != "A" else "B") + signature[1:]))
    assert gql("query{me{login}}", token=forged)[0] == 401
    expired = jwt.encode({**claims, "exp": int(time()) - 1},
                         conf["LAB5_JWT_SECRET"], algorithm="HS256")
    assert gql("query{me{login}}", token=expired)[0] == 401
    cache = redis.Redis(host="127.0.0.1", port=57579,
                        password=conf["LAB5_REDIS_PASSWORD"], decode_responses=True)
    key = "lab5:session:" + claims["jti"]
    assert cache.get(key) == claims["sub"]
    assert 0 < cache.ttl(key) <= 1800
    user = data("query{me{login role}}", token=token,
                extra_headers={"X-Demo-Actor": "admin"})["me"]
    assert user == {"login": "manager", "role": "MANAGER"}
    assert data("mutation{signOut}", token=token)["signOut"] is True
    assert cache.exists(key) == 0
    assert gql("query{me{login}}", token=token)[0] == 401


def test_gateway_and_service_role_policy():
    admin, manager, analyst = login("admin"), login("manager"), login("analyst")
    assert data("query{me{role}}", token=admin)["me"]["role"] == "ADMIN"
    assert data("query{me{role}}", token=analyst)["me"]["role"] == "ANALYST"
    assert gql("query{transactionSummary{transactionCount}}", token=admin)[0] == 403
    assert gql("query{transactionSummary{transactionCount}}", token=analyst)[0] == 403
    assert gql("query{alias:transactionSummary{transactionCount}}", token=analyst)[0] == 403
    assert gql("query{...Protected} fragment Protected on Query{transactionSummary{transactionCount}}", token=analyst)[0] == 403
    assert data("query{clients{totalCount}}", token=analyst)["clients"]["totalCount"] >= 2
    create = "mutation($x:ClientInput!){createClient(input:$x){id externalId}}"
    values = {"x": {"externalId": "SEC-" + uuid4().hex,
                    "displayName": "Учебный клиент безопасности",
                    "idempotencyKey": uuid4().hex}}
    assert gql(create, values, analyst)[0] == 403
    created = data(create, values, admin)["createClient"]
    assert created["externalId"] == values["x"]["externalId"]
    assert data("query{transactionSummary{transactionCount}}", token=manager)["transactionSummary"]["transactionCount"] >= 30
    own = data("query($id:ID!){reviewCase(id:$id){id assigneeId}}",
               {"id": CASE_ID}, analyst)["reviewCase"]
    assert own and own["assigneeId"] == "c7fba0b2-b5bd-59e7-b722-4f0e6c5b4c45"
    ids = __import__('json').loads((ROOT / 'docs/lab3/demo_ids.json').read_text())
    investigation = data("query($tx:ID!,$result:ID!){transaction(id:$tx){id amount} analysisResult(id:$result){id hits{ruleCode}}}",
                         {"tx": ids['transaction'], "result": ids['result2']}, analyst)
    assert investigation['transaction']['id'] == ids['transaction']
    assert investigation['analysisResult']['hits']
    tx = data("mutation($x:TransactionInput!){registerTransaction(input:$x){id}}",
              {"x": {"source": "lab5_analyst", "externalId": uuid4().hex,
                     "accountId": ids['account'], "amount": "10.00", "currency": "BYN",
                     "direction": "OUT", "occurredAt": "2026-10-18T12:00:00Z",
                     "idempotencyKey": uuid4().hex}}, analyst)['registerTransaction']
    assert tx['id']
    # A report remains private to its author even when its UUID is known.
    own_report = str(uuid4())
    conf = settings()
    with psycopg.connect(f"postgresql://bank_case:{conf['LAB5_DB_PASSWORD']}@127.0.0.1:57534/bank_case") as conn:
        conn.execute("INSERT INTO reports(id,author_id,period_start,period_end,filters,snapshot,created_at) VALUES (%s,%s,'2026-09-01','2026-10-01','{}','{\"totalCases\":1}',now())",
                     (own_report, own['assigneeId']))
    assert data("query($id:ID!){report(id:$id){id}}", {"id": own_report}, analyst)['report']['id'] == own_report
    assert data("query($id:ID!){report(id:$id){id}}", {"id": ids['report']}, analyst)['report'] is None
    assert data("query($id:ID!){exportReport(id:$id){contentBase64}}", {"id": own_report}, analyst)['exportReport']['contentBase64']


def test_admin_registration_role_change_block_and_row_scope():
    admin = login("admin")
    suffix = uuid4().hex[:10]
    staff_login = "analyst_" + suffix
    staff_password = "Study-" + uuid4().hex + "!"
    register = "mutation($x:StaffInput!){registerStaff(input:$x){id login role isActive}}"
    values = {"x": {"login": staff_login, "password": staff_password,
                    "roleCode": "ANALYST", "idempotencyKey": uuid4().hex}}
    person = data(register, values, admin)["registerStaff"]
    assert person["login"] == staff_login and person["role"] == "ANALYST"
    assert data(register, values, admin)["registerStaff"] == person
    conf = settings()
    with psycopg.connect(f"postgresql://bank_auth:{conf['LAB5_DB_PASSWORD']}@127.0.0.1:57531/bank_auth") as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE id=%s", (person["id"],)).fetchone()[0]
    assert stored.startswith("pbkdf2_sha256$600000$") and staff_password not in stored
    user_token = login(staff_login, staff_password)
    assert data("query{me{role}}", token=user_token)["me"]["role"] == "ANALYST"
    assert data("query($id:ID!){reviewCase(id:$id){id}}", {"id": CASE_ID}, user_token)["reviewCase"] is None
    assert data("query{reviewCases{totalCount}}", token=user_token)["reviewCases"]["totalCount"] == 0
    role = data("mutation($id:ID!,$k:String!){changeStaffRole(userId:$id,roleCode:MANAGER,idempotencyKey:$k){id role}}",
                {"id": person["id"], "k": uuid4().hex}, admin)["changeStaffRole"]
    assert role["role"] == "MANAGER"
    assert data("query{transactionSummary{transactionCount}}", token=user_token)["transactionSummary"]["transactionCount"] >= 30
    blocked = data("mutation($id:ID!,$k:String!){blockStaff(userId:$id,idempotencyKey:$k){id isActive}}",
                   {"id": person["id"], "k": uuid4().hex}, admin)["blockStaff"]
    assert blocked["isActive"] is False
    assert gql("query{me{login}}", token=user_token)[0] == 401
    assert gql("mutation($n:String!,$p:String!){signIn(login:$n,password:$p){accessToken}}",
               {"n": staff_login, "p": staff_password})[1]["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


def test_redis_expiration_denies_still_signed_jwt():
    token = login("manager")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - time() > 60
    conf = settings()
    cache = redis.Redis(host="127.0.0.1", port=57579,
                        password=conf["LAB5_REDIS_PASSWORD"], decode_responses=True)
    key = "lab5:session:" + claims["jti"]
    assert cache.expire(key, 1)
    sleep(1.3)
    assert cache.exists(key) == 0
    assert gql("query{me{login}}", token=token)[0] == 401
