"""Temporary in-process ports; no gRPC or Kafka imports."""
from back.lab3.mocks import MockTransactionClient as ReadTransactionClient
from back.lab3.mocks import MockCaseClient as ReadCaseClient


class MockTransactionClient(ReadTransactionClient):
    def create_client(self, actor, input):return self._invoke('create_client',actor=actor,input=input)
    def open_account(self, actor, input):return self._invoke('open_account',actor=actor,input=input)
    def register_counterparty(self, actor, input):return self._invoke('register_counterparty',actor=actor,input=input)
    def register_transaction(self, actor, input):return self._invoke('register_transaction',actor=actor,input=input)
    def transaction_summary(self, filter=None):return self._invoke('transaction_summary',filter=filter)


class MockCaseClient(ReadCaseClient):
    def take_case(self, actor, caseId, expectedVersion, idempotencyKey):
        return self._invoke('take_case',actor=actor,caseId=caseId,expectedVersion=expectedVersion,idempotencyKey=idempotencyKey)
    def add_case_comment(self, actor, input):return self._invoke('add_case_comment',actor=actor,input=input)
    def escalate_case(self, actor, caseId, reason, expectedVersion, idempotencyKey):
        return self._invoke('escalate_case',actor=actor,caseId=caseId,reason=reason,expectedVersion=expectedVersion,idempotencyKey=idempotencyKey)
    def close_case(self, actor, input):return self._invoke('close_case',actor=actor,input=input)
    def reopen_case(self, actor, caseId, reason, expectedVersion, idempotencyKey):
        return self._invoke('reopen_case',actor=actor,caseId=caseId,reason=reason,expectedVersion=expectedVersion,idempotencyKey=idempotencyKey)
    def mark_notification_read(self, actor, id):return self._invoke('mark_notification_read',actor=actor,id=id)
