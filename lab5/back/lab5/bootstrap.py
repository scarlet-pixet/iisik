"""Compose authenticated identity with unchanged LR4 business services."""
from dataclasses import dataclass
from types import SimpleNamespace
import os

from back.lab3.auth.models import User
from back.lab3.analysis.repository import AnalysisRepository
from back.lab3.analysis.service import AnalysisService
from back.lab3.mocks import MockAnalysisClient
from back.lab4.common import WritableDatabase
from back.lab4.transaction.repository import TransactionRepository
from back.lab4.transaction.service import TransactionService
from back.lab4.mocks import MockTransactionClient, MockCaseClient
from .case import CaseRepository, CaseService


class PrincipalClient:
    """Supplies only the principal already validated by Auth Service."""
    def __init__(self, actor):
        self.actor = actor

    def get_current_user(self):
        return self.actor


@dataclass
class Container:
    databases: dict
    transaction_service: TransactionService
    analysis_repository: AnalysisRepository
    case_repository: CaseRepository

    def clients(self, verified):
        actor = User(id=verified["id"], login=verified["login"],
                     role=verified["role"], is_active=verified["isActive"])
        principal = PrincipalClient(actor)
        transaction = MockTransactionClient(self.transaction_service)
        analysis = MockAnalysisClient(AnalysisService(self.analysis_repository, transaction))
        case = MockCaseClient(CaseService(self.case_repository, principal))
        return SimpleNamespace(auth=principal, transaction=transaction,
                               analysis=analysis, case=case)


def build():
    names = ("transaction", "analysis", "case")
    databases = {name: WritableDatabase(os.environ[f"LAB5_{name.upper()}_DSN"], name)
                 for name in names}
    return Container(databases,
                     TransactionService(TransactionRepository(databases["transaction"])),
                     AnalysisRepository(databases["analysis"]),
                     CaseRepository(databases["case"]))
