from dataclasses import dataclass
from types import SimpleNamespace
import os

from back.lab3.auth.repository import AuthRepository
from back.lab3.auth.service import AuthService
from back.lab3.analysis.repository import AnalysisRepository
from back.lab3.analysis.service import AnalysisService
from back.lab3.mocks import MockAuthClient, MockAnalysisClient
from back.lab4.common import WritableDatabase
from back.lab4.transaction.repository import TransactionRepository
from back.lab4.transaction.service import TransactionService
from back.lab4.case.repository import CaseRepository
from back.lab4.case.service import CaseService
from back.lab4.mocks import MockTransactionClient, MockCaseClient


ACTORS = {
    'admin':'b4703b75-0c9e-55cf-8ad2-bd607b00f7ed',
    'analyst':'c7fba0b2-b5bd-59e7-b722-4f0e6c5b4c45',
    'manager':'43817961-b437-5313-9754-19535c80b1b9',
}


@dataclass
class Container:
    databases:dict
    auth_repository:AuthRepository
    transaction_service:TransactionService
    analysis_repository:AnalysisRepository
    case_repository:CaseRepository

    def clients(self, actor_name):
        actor_id = ACTORS.get(actor_name)
        if actor_id is None: raise ValueError('Unknown demo actor')
        auth = MockAuthClient(AuthService(self.auth_repository,actor_id))
        transaction = MockTransactionClient(self.transaction_service)
        analysis = MockAnalysisClient(AnalysisService(self.analysis_repository,transaction))
        case = MockCaseClient(CaseService(self.case_repository,auth))
        return SimpleNamespace(auth=auth,transaction=transaction,analysis=analysis,case=case)


def build():
    if os.getenv('LAB4_TRANSPORT','mock') != 'mock':
        raise RuntimeError('ЛР4 допускает только mock transport')
    names=('auth','transaction','analysis','case')
    databases={name:WritableDatabase(
        os.getenv('LAB4_'+name.upper()+'_DSN',f'postgresql://bank_{name}:lab4_owner_only@127.0.0.1:{57431+i}/bank_{name}'),
        name,
    ) for i,name in enumerate(names)}
    return Container(databases,AuthRepository(databases['auth']),
                     TransactionService(TransactionRepository(databases['transaction'])),
                     AnalysisRepository(databases['analysis']),CaseRepository(databases['case']))
