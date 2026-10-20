"""Case read access is scoped to the authenticated analyst's own queue."""
from back.lab3.common import DomainError, uuid, period, pagination, paged, model
from back.lab3.case.models import Report
from back.lab4.case.repository import CaseRepository as BaseCaseRepository
from back.lab4.case.service import CaseService as BaseCaseService


class CaseRepository(BaseCaseRepository):
    def report_visible_to(self, id, author_id):
        return model(Report, self.db.one(
            "SELECT * FROM reports WHERE id=%s AND author_id=%s", (id, author_id)))

    def cases_visible_to(self, filters, page, analyst_id):
        clauses = ["(assignee_id=%s OR (assignee_id IS NULL AND status='NEW'))"]
        params = [analyst_id]
        for key, column in (("status", "status"), ("priority", "priority"),
                            ("assigneeId", "assignee_id"), ("clientId", "client_id")):
            if key in filters:
                clauses.append(column + "=%s")
                params.append(filters[key])
        if "period" in filters:
            clauses.extend(["created_at >= %s", "created_at < %s"])
            params.extend(filters["period"])
        rows, total = self.page_rows("SELECT * FROM review_cases", clauses, params, page)
        return self.enrich(rows), total


class CaseService(BaseCaseService):
    def get_report(self, id):
        actor = self.auth_client.get_current_user()
        if actor.role == "ANALYST":
            return self.repository.report_visible_to(uuid(id), actor.id)
        return super().get_report(id)

    def get_case(self, id):
        actor = self.auth_client.get_current_user()
        result = self.repository.case(uuid(id))
        if actor.role == "ANALYST" and result and not (
            result.assignee_id == actor.id or
            (result.assignee_id is None and result.status == "NEW")
        ):
            return None
        return result

    def search_cases(self, filter=None, page=None):
        actor = self.auth_client.get_current_user()
        if actor.role != "ANALYST":
            return super().search_cases(filter, page)
        filters = dict(filter or {})
        for key in ("clientId", "assigneeId"):
            if key in filters:
                filters[key] = uuid(filters[key])
        if "period" in filters:
            filters["period"] = period(filters["period"])
        if "status" in filters and filters["status"] not in (
            "NEW", "ASSIGNED", "IN_PROGRESS", "ESCALATED", "CLOSED"
        ):
            raise DomainError("BAD_INPUT", "Неизвестный статус")
        if "priority" in filters and filters["priority"] not in ("LOW", "MEDIUM", "HIGH"):
            raise DomainError("BAD_INPUT", "Неизвестный приоритет")
        spec = pagination(page, {"id": "id", "createdAt": "created_at",
                                 "latestScore": "latest_score"}, "createdAt")
        rows, total = self.repository.cases_visible_to(filters, spec, actor.id)
        return paged(rows, total, spec, page)
