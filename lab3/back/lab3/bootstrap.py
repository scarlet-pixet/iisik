"""Composition root: the only place aware of all concrete components."""
from dataclasses import dataclass
from .config import Settings
from .common import Database
from .auth.repository import AuthRepository
from .auth.service import AuthService
from .transaction.repository import TransactionRepository
from .transaction.service import TransactionService
from .analysis.repository import AnalysisRepository
from .analysis.service import AnalysisService
from .case.repository import CaseRepository
from .case.service import CaseService
from .mocks import MockAuthClient,MockTransactionClient,MockAnalysisClient,MockCaseClient
from .ports import AuthReadPort,TransactionReadPort,AnalysisReadPort,CaseReadPort

@dataclass(frozen=True)
class Clients:
    auth:AuthReadPort
    transaction:TransactionReadPort
    analysis:AnalysisReadPort
    case:CaseReadPort

@dataclass
class Container:
    clients:Clients
    databases:dict[str,Database]

def build(settings=None):
    settings=settings or Settings.load()
    db={name:Database(dsn,name) for name,dsn in settings.databases.items()}
    auth=MockAuthClient(AuthService(AuthRepository(db['auth']),settings.actor_id))
    transaction=MockTransactionClient(TransactionService(TransactionRepository(db['transaction'])))
    analysis=MockAnalysisClient(AnalysisService(AnalysisRepository(db['analysis']),transaction))
    case=MockCaseClient(CaseService(CaseRepository(db['case']),auth))
    return Container(Clients(auth,transaction,analysis,case),db)
