"""In-process stubs call public service methods, never another repository.

These are temporary transport replacements, not fabricated database responses.
Deep copies keep the boundary free of shared mutable DTOs. No network I/O here.
"""
from copy import deepcopy
import logging
from .ports import AuthReadPort, TransactionReadPort, AnalysisReadPort, CaseReadPort
log=logging.getLogger('lab3.mock')

class MockClient:
    def __init__(self, service):self._service=service
    def _invoke(self,method,**kwargs):
        log.info('MOCK %s.%s',type(self._service).__name__,method)
        return deepcopy(getattr(self._service,method)(**deepcopy(kwargs)))

class MockAuthClient(MockClient,AuthReadPort):
    def get_current_user(self):return self._invoke('get_current_user')

class MockTransactionClient(MockClient,TransactionReadPort):
    def get_client(self,id):return self._invoke('get_client',id=id)
    def get_transaction(self,id):return self._invoke('get_transaction',id=id)
    def search_clients(self,filter=None,page=None):return self._invoke('search_clients',filter=filter,page=page)
    def search_transactions(self,filter=None,page=None):return self._invoke('search_transactions',filter=filter,page=page)

class MockAnalysisClient(MockClient,AnalysisReadPort):
    def get_profile(self,id):return self._invoke('get_profile',id=id)
    def get_result(self,id):return self._invoke('get_result',id=id)
    def get_run(self,id):return self._invoke('get_run',id=id)
    def list_rule_versions(self,ruleId):return self._invoke('list_rule_versions',ruleId=ruleId)
    def compare_runs(self,firstId,secondId):return self._invoke('compare_runs',firstId=firstId,secondId=secondId)
    def get_client_activity(self,clientId,period,currency,runId):return self._invoke('get_client_activity',clientId=clientId,period=period,currency=currency,runId=runId)

class MockCaseClient(MockClient,CaseReadPort):
    def get_case(self,id):return self._invoke('get_case',id=id)
    def search_cases(self,filter=None,page=None):return self._invoke('search_cases',filter=filter,page=page)
    def get_report(self,id):return self._invoke('get_report',id=id)
    def export_report(self,id):return self._invoke('export_report',id=id)
    def list_notifications(self,unreadOnly=None,page=None):return self._invoke('list_notifications',unreadOnly=unreadOnly,page=page)
