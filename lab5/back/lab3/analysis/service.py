from back.lab3.common import uuid, period, currency, DomainError
from back.lab3.ports import TransactionReadPort

class AnalysisService:
    def __init__(self, repository, transaction_client: TransactionReadPort):
        self.repository,self.transaction_client=repository,transaction_client
    def get_profile(self,id):return self.repository.profile(uuid(id))
    def get_result(self,id):return self.repository.result(uuid(id))
    def get_run(self,id):return self.repository.run(uuid(id))
    def list_rule_versions(self,ruleId):return self.repository.rule_versions(uuid(ruleId))
    def compare_runs(self,firstId,secondId):
        firstId,secondId=uuid(firstId),uuid(secondId)
        if not self.repository.run(firstId) or not self.repository.run(secondId):raise DomainError('NOT_FOUND','Один из запусков не найден')
        a,b=self.repository.run_results(firstId),self.repository.run_results(secondId)
        common=sorted(a.keys()&b.keys()); ah,bh=self.repository.hit_codes(firstId),self.repository.hit_codes(secondId)
        return {'commonCount':len(common),'onlyFirstCount':len(a.keys()-b.keys()),'onlySecondCount':len(b.keys()-a.keys()),
            'changedScores':[{'transactionId':id,'before':a[id]['score'],'after':b[id]['score']} for id in common if a[id]['score']!=b[id]['score']],
            'newHits':[{'transactionId':id,'rules':sorted(bh.get(id,set())-ah.get(id,set()))} for id in common if bh.get(id,set())-ah.get(id,set())]}
    def get_client_activity(self,clientId,period:dict,currency:str,runId):
        from back.lab3.common import period as valid_period, currency as valid_currency
        clientId,runId=uuid(clientId),uuid(runId);valid_period(period);valid_currency(currency)
        if not self.repository.run(runId):raise DomainError('NOT_FOUND','Запуск не найден')
        client=self.transaction_client.get_client(clientId)
        if client is None:raise DomainError('NOT_FOUND','Клиент не найден')
        transactions=[];cursor=None
        while True:
            response=self.transaction_client.search_transactions(filter={'clientId':clientId,'period':period,'currency':currency},page={'limit':100,'cursor':cursor})
            transactions.extend(response['items']);cursor=response['nextCursor']
            if not cursor:break
            if len(transactions)>=10000:raise DomainError('BAD_INPUT','Обзор ограничен 10000 операциями; сократите период')
        results=self.repository.run_results(runId);distribution={'0-29':0,'30-59':0,'60-79':0,'80-100':0,'notAnalyzed':0}
        for t in transactions:
            r=results.get(t.id)
            key='notAnalyzed' if r is None else '0-29' if r['score']<30 else '30-59' if r['score']<60 else '60-79' if r['score']<80 else '80-100'
            distribution[key]+=1
        return {'client':client,'currency':currency,'transactions':transactions,'profiles':self.repository.profiles(clientId,runId,currency),'scoreDistribution':distribution,'partialErrors':[]}
