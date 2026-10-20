"""Run against the actual LR3 Compose stack: python -m pytest tests/lab3 -q."""
import ast, base64, hashlib, json, os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import psycopg
from psycopg import sql
import pytest
import requests
from graphql import build_schema
from back.lab3.config import Settings
from back.lab3.common import DomainError
from back.lab3.analysis.service import AnalysisService
from back.lab3.mocks import MockTransactionClient

ROOT = Path(__file__).resolve().parents[2]
IDS = json.loads((ROOT/'docs/lab3/demo_ids.json').read_text())
URL = os.getenv('LAB3_TEST_URL', 'http://127.0.0.1:18003')
PERIOD = '{from:"2026-09-01T00:00:00Z",to:"2026-10-01T00:00:00Z"}'
MISSING = '00000000-0000-0000-0000-000000000001'

def call(query, variables=None, errors=False):
    response = requests.post(URL+'/graphql', json={'query':query,'variables':variables or {}}, timeout=30)
    response.raise_for_status()
    result = response.json()
    if not errors: assert not result.get('errors'), result
    return result if errors else result['data']

def fingerprints():
    out = {}
    for owner,dsn in Settings.load().databases.items():
        with psycopg.connect(dsn) as conn:
            tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
            for (name,) in tables:
                rows = conn.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text').format(sql.Identifier(name))).fetchall()
                out[owner+'.'+name] = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
    return out

@pytest.fixture(scope='session', autouse=True)
def unchanged_databases():
    before = fingerprints()
    yield
    after = fingerprints()
    assert before == after, 'Queries must not mutate any table'
    target = ROOT/'docs/lab3/evidence/database-fingerprints.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'unchanged':True,'tableCount':len(before),'sha256':after},indent=2))

QUERIES = {
 'me':'me {id login role isActive}',
 'clients':'clients {totalCount nextCursor items {id externalId displayName segment isActive accounts {id clientId externalId currency status}}}',
 'transactions':'transactions(page:{limit:100}) {totalCount nextCursor items {id externalId source clientId accountId counterpartyId amount currency direction occurredAt ingestedAt}}',
 'transaction':f'transaction(id:"{IDS["transaction"]}") {{id amount currency direction occurredAt}}',
 'clientActivity':f'clientActivity(clientId:"{IDS["client"]}",runId:"{IDS["run2"]}",currency:"BYN",period:{PERIOD}) {{client{{id accounts{{id}}}} transactions{{id amount}} profiles{{id sampleSize}} scoreDistribution partialErrors}}',
 'profile':f'profile(id:"{IDS["profile2"]}") {{id runId clientId currency direction windowStart windowEnd cutoffTransactionId ingestedBefore sampleSize medianAmount madAmount metrics dataStatus}}',
 'analysisResult':f'analysisResult(id:"{IDS["result2"]}") {{id transactionId runId profileId score threshold dataStatus missingReasons calculatedAt hits{{ruleCode version featureValue limitValue contribution}}}}',
 'analysisRun':f'analysisRun(id:"{IDS["run2"]}") {{id mode status counters createdAt completedAt}}',
 'compareRuns':f'compareRuns(firstId:"{IDS["run1"]}",secondId:"{IDS["run2"]}") {{commonCount onlyFirstCount onlySecondCount changedScores newHits}}',
 'ruleVersions':f'ruleVersions(ruleId:"{IDS["AMOUNT"]}") {{id ruleId version weight parameters status publishedAt}}',
 'reviewCases':'reviewCases {totalCount nextCursor items {id latestScore status priority comments{id text} decisions{id outcome}}}',
 'reviewCase':f'reviewCase(id:"{IDS["case"]}") {{id transactionId clientId latestResultId latestScore status priority assigneeId reviewCycle rowVersion comments{{id authorId kind text createdAt}} decisions{{id authorId reviewCycle outcome reason decidedAt}}}}',
 'report':f'report(id:"{IDS["report"]}") {{id periodStart periodEnd filters snapshot createdAt}}',
 'exportReport':f'exportReport(id:"{IDS["report"]}") {{fileName mediaType contentBase64}}',
 'notifications':'notifications {totalCount nextCursor items {id caseId type createdAt readAt}}',
}

@pytest.mark.parametrize('name', QUERIES)
def test_all_15_queries(name):
    data=call('{'+QUERIES[name]+'}')[name]
    assert data is not None
    output=ROOT/'docs/lab3/evidence/queries'; output.mkdir(parents=True,exist_ok=True)
    (output/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def test_read_contract_and_health():
    health=requests.get(URL+'/health',timeout=20).json()
    assert health['transport']=='mock-in-process' and health['allReady'] and not health['grpcLoaded'] and not health['kafkaLoaded']
    schema=build_schema(requests.get(URL+'/schema.graphql',timeout=10).text)
    original=build_schema((ROOT/'back/contracts/schema.graphql').read_text())
    assert schema.mutation_type is None
    assert set(schema.query_type.fields)==set(QUERIES)==set(original.query_type.fields)
    for name,field in schema.query_type.fields.items():
        old=original.query_type.fields[name]
        assert str(field.type)==str(old.type)
        assert {k:str(v.type) for k,v in field.args.items()}=={k:str(v.type) for k,v in old.args.items()}
    assert 'password' not in str(schema.get_type('User').fields)

def test_business_results_and_relations():
    data=call('{'+ ' '.join(QUERIES.values())+'}')
    assert data['me']['role']=='MANAGER'
    assert data['clients']['totalCount']==2
    assert all(c['accounts'] for c in data['clients']['items'])
    assert data['transactions']['totalCount']==30
    assert data['transaction']['amount']=='5000.00'
    assert data['analysisResult']['score']==85
    assert {h['ruleCode'] for h in data['analysisResult']['hits']}=={'AMOUNT','FREQUENCY'}
    case=data['reviewCase']
    assert case['comments'] and case['decisions'][0]['outcome']=='EXPLAINED'
    assert case['latestResultId']==data['analysisResult']['id']
    activity=data['clientActivity']
    assert activity['scoreDistribution']=={'0-29':1,'30-59':0,'60-79':0,'80-100':1,'notAnalyzed':28}
    assert len(activity['transactions'])==30 and activity['profiles'][0]['sampleSize']==29
    comp=data['compareRuns']
    assert [comp[k] for k in ('commonCount','onlyFirstCount','onlySecondCount')]==[1,1,1]
    assert comp['changedScores']==[{'transactionId':IDS['transaction'],'before':60,'after':85}]
    assert comp['newHits']==[{'transactionId':IDS['transaction'],'rules':['FREQUENCY']}]
    content=base64.b64decode(data['exportReport']['contentBase64']).decode('utf-8-sig')
    assert 'closedCases,1' in content and 'totalCases,1' in content

@pytest.mark.parametrize('field',['transaction','profile','analysisResult','analysisRun','reviewCase','report'])
def test_missing_object_is_null(field):
    assert call('{'+f'{field}(id:"{MISSING}"){{id}}'+'}')[field] is None

@pytest.mark.parametrize('args', ['page:{limit:0}','page:{limit:101}','page:{sortBy:"id; DROP TABLE users"}', 'page:{cursor:"broken"}', 'filter:{currency:"byn"}','filter:{amountFrom:"100",amountTo:"5"}','filter:{period:{from:"2026-10-01T00:00:00Z",to:"2026-09-01T00:00:00Z"}}'])
def test_bad_input(args):
    result=call('{transactions('+args+'){totalCount}}',errors=True)
    assert result['errors'][0]['extensions']['code']=='BAD_INPUT'

def test_empty_filters_and_unread():
    data=call('{ clients(filter:{externalId:"absent"}){totalCount items{id}} reviewCases(filter:{status:NEW}){totalCount} notifications(unreadOnly:true){totalCount items{readAt}} }')
    assert data['clients']=={'totalCount':0,'items':[]}
    assert data['reviewCases']['totalCount']==0
    assert data['notifications']=={'totalCount':1,'items':[{'readAt':None}]}
    q=QUERIES['clientActivity'].replace(IDS['client'],IDS['emptyClient'])
    empty=call('{'+q+'}')['clientActivity']
    assert empty['transactions']==[] and empty['profiles']==[] and sum(empty['scoreDistribution'].values())==0

def test_pagination_and_amount_period_filters():
    q='query($p:PageInput){transactions(page:$p){totalCount nextCursor items{id}}}'
    cursor=None; seen=[]
    while True:
        data=call(q,{'p':{'limit':7,'cursor':cursor}})['transactions']
        seen.extend(x['id'] for x in data['items']);cursor=data['nextCursor']
        if cursor is None:break
    assert len(seen)==len(set(seen))==30
    filtered=call('{transactions(filter:{amountFrom:"1000",currency:"BYN",period:'+PERIOD+'}){totalCount items{id}}}')['transactions']
    assert filtered=={'totalCount':1,'items':[{'id':IDS['transaction']}]}

def test_missing_required_and_invalid_uuid_and_no_mutation():
    for query,code in [('{transaction(id:"bad"){id}}','BAD_INPUT'),('{exportReport(id:"'+MISSING+'"){fileName}}','NOT_FOUND'),('{compareRuns(firstId:"'+IDS['run1']+'",secondId:"'+MISSING+'"){commonCount}}','NOT_FOUND')]:
        assert call(query,errors=True)['errors'][0]['extensions']['code']==code
    assert call('mutation{__typename}',errors=True)['errors']

@pytest.mark.parametrize('owner',['auth','transaction','analysis','case'])
def test_database_privileges(owner):
    with psycopg.connect(Settings.load().databases[owner]) as conn:
        assert conn.execute('SHOW default_transaction_read_only').fetchone()[0]=='on'
        rows=conn.execute("SELECT tablename,has_table_privilege(current_user,quote_ident(tablename),'INSERT,UPDATE,DELETE,TRUNCATE') FROM pg_tables WHERE schemaname='public'").fetchall()
        assert rows and not any(row[1] for row in rows)
        assert conn.execute('SELECT current_database()').fetchone()[0]=='bank_'+owner
        assert conn.execute("SELECT datname FROM pg_database WHERE datname LIKE 'bank_%'").fetchall()==[('bank_'+owner,)]
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute(sql.SQL('DELETE FROM {} WHERE false').format(sql.Identifier(rows[0][0])))

def test_mock_boundary_injection_and_copy():
    repo=Mock();repo.run.return_value=object();repo.run_results.return_value={};repo.profiles.return_value=[]
    target=Mock();target.get_client.return_value=SimpleNamespace(id=IDS['client'])
    target.search_transactions.return_value={'items':[],'nextCursor':None}
    client=MockTransactionClient(target)
    result=AnalysisService(repo,client).get_client_activity(IDS['client'],{'from':'2026-09-01T00:00:00Z','to':'2026-10-01T00:00:00Z'},'BYN',IDS['run1'])
    assert result['transactions']==[]
    target.get_client.assert_called_once_with(id=IDS['client'])
    target.search_transactions.assert_called_once()
    assert client.get_client(IDS['client']) is not target.get_client.return_value
    target.search_transactions.side_effect=DomainError('DEPENDENCY_UNAVAILABLE','temporary failure')
    with pytest.raises(DomainError,match='temporary failure'):
        AnalysisService(repo,client).get_client_activity(IDS['client'],{'from':'2026-09-01T00:00:00Z','to':'2026-10-01T00:00:00Z'},'BYN',IDS['run1'])

def test_service_dependency_boundaries():
    for owner in ('auth','transaction','analysis','case'):
        for path in (ROOT/'back/lab3'/owner).glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.ImportFrom):
                    module=node.module or ''
                    assert not any(module.startswith('back.lab3.'+other+'.repository') for other in ('auth','transaction','analysis','case') if other!=owner)
                    assert 'graphql' not in module and 'grpc' not in module
    for path in (ROOT/'back/lab3/graphql').glob('*.py'):
        if path.name=='app.py':continue
        assert '.repository' not in path.read_text(encoding='utf-8')
