from uuid import uuid4

from back.lab3.case.service import CaseService as ReadService
from back.lab3.common import DomainError, uuid
from back.lab4.common import require_role, required_text


class CaseService(ReadService):
    def _change(self, actor, name, key, payload, perform, roles=('ANALYST',)):
        require_role(actor, *roles)

        def locked(conn):
            row = conn.execute('SELECT * FROM review_cases WHERE id=%s FOR UPDATE', (payload['caseId'],)).fetchone()
            if row is None: raise DomainError('NOT_FOUND', 'Случай не найден')
            perform(conn, row)
            return payload['caseId']

        result = self.repository.execute(actor, name, key, payload, locked)
        return self.repository.case(result)

    @staticmethod
    def _version(row, expected):
        if row['row_version'] != expected:
            raise DomainError('CONFLICT', 'Версия случая изменилась; перечитайте его перед повтором')

    def take_case(self, actor, caseId, expectedVersion, idempotencyKey):
        case_id = uuid(caseId)
        if expectedVersion < 1: raise DomainError('BAD_INPUT', 'expectedVersion должен быть положительным')
        payload = {'caseId': case_id, 'expectedVersion': expectedVersion}

        def perform(conn, row):
            self._version(row, expectedVersion)
            if row['status'] not in ('NEW', 'ASSIGNED') or (row['assignee_id'] and str(row['assignee_id']) != actor.id):
                raise DomainError('CONFLICT', 'Случай нельзя взять в работу')
            conn.execute("UPDATE review_cases SET status='IN_PROGRESS',assignee_id=%s,row_version=row_version+1,updated_at=now() WHERE id=%s",
                         (actor.id, case_id))

        return self._change(actor, 'takeCase', idempotencyKey, payload, perform)

    def add_case_comment(self, actor, input):
        case_id = uuid(input['caseId'])
        text = required_text(input['text'], 'text', 4000)
        payload = {'caseId': case_id, 'text': text}

        def perform(conn, row):
            if row['status'] == 'CLOSED' or str(row['assignee_id']) != actor.id:
                raise DomainError('CONFLICT', 'Комментировать может назначенный аналитик до закрытия')
            conn.execute('INSERT INTO case_comments(id,case_id,author_id,kind,text,created_at) VALUES (%s,%s,%s,%s,%s,now())',
                         (str(uuid4()), case_id, actor.id, 'COMMENT', text))
            conn.execute('UPDATE review_cases SET row_version=row_version+1,updated_at=now() WHERE id=%s', (case_id,))

        return self._change(actor, 'addCaseComment', input['idempotencyKey'], payload, perform)

    def escalate_case(self, actor, caseId, reason, expectedVersion, idempotencyKey):
        case_id = uuid(caseId)
        reason = required_text(reason, 'reason', 4000)
        if expectedVersion < 1: raise DomainError('BAD_INPUT', 'expectedVersion должен быть положительным')
        payload = {'caseId': case_id, 'reason': reason, 'expectedVersion': expectedVersion}

        def perform(conn, row):
            self._version(row, expectedVersion)
            if row['status'] != 'IN_PROGRESS' or str(row['assignee_id']) != actor.id:
                raise DomainError('CONFLICT', 'Эскалация доступна назначенному аналитику в работе')
            conn.execute('INSERT INTO case_comments(id,case_id,author_id,kind,text,created_at) VALUES (%s,%s,%s,%s,%s,now())',
                         (str(uuid4()), case_id, actor.id, 'ESCALATION', reason))
            conn.execute("UPDATE review_cases SET status='ESCALATED',priority='HIGH',row_version=row_version+1,updated_at=now() WHERE id=%s",
                         (case_id,))

        return self._change(actor, 'escalateCase', idempotencyKey, payload, perform)

    def close_case(self, actor, input):
        case_id = uuid(input['caseId'])
        reason = required_text(input['reason'], 'reason', 4000)
        version = input['expectedVersion']
        if version < 1: raise DomainError('BAD_INPUT', 'expectedVersion должен быть положительным')
        outcome = input['outcome']
        if outcome not in ('UNUSUAL_CONFIRMED', 'EXPLAINED'):
            raise DomainError('BAD_INPUT', 'Некорректное решение')
        payload = {'caseId': case_id, 'reason': reason, 'expectedVersion': version, 'outcome': outcome}

        def perform(conn, row):
            self._version(row, version)
            if row['status'] not in ('IN_PROGRESS', 'ESCALATED') or (
                actor.role == 'ANALYST' and str(row['assignee_id']) != actor.id
            ):
                raise DomainError('CONFLICT', 'Решение может принять назначенный аналитик или руководитель')
            conn.execute('INSERT INTO case_decisions(id,case_id,author_id,review_cycle,outcome,reason,decided_at) VALUES (%s,%s,%s,%s,%s,%s,now())',
                         (str(uuid4()), case_id, actor.id, row['review_cycle'], outcome, reason))
            conn.execute("UPDATE review_cases SET status='CLOSED',row_version=row_version+1,updated_at=now() WHERE id=%s", (case_id,))

        return self._change(actor, 'closeCase', input['idempotencyKey'], payload, perform,
                            roles=('ANALYST','MANAGER'))

    def reopen_case(self, actor, caseId, reason, expectedVersion, idempotencyKey):
        case_id = uuid(caseId)
        reason = required_text(reason, 'reason', 4000)
        if expectedVersion < 1: raise DomainError('BAD_INPUT', 'expectedVersion должен быть положительным')
        payload = {'caseId': case_id, 'reason': reason, 'expectedVersion': expectedVersion}

        def perform(conn, row):
            self._version(row, expectedVersion)
            if row['status'] != 'CLOSED': raise DomainError('CONFLICT', 'Повторное открытие возможно только после решения')
            conn.execute('INSERT INTO case_comments(id,case_id,author_id,kind,text,created_at) VALUES (%s,%s,%s,%s,%s,now())',
                         (str(uuid4()), case_id, actor.id, 'REOPEN', reason))
            conn.execute("UPDATE review_cases SET status='NEW',assignee_id=NULL,review_cycle=review_cycle+1,row_version=row_version+1,updated_at=now() WHERE id=%s", (case_id,))

        return self._change(actor, 'reopenCase', idempotencyKey, payload, perform,
                            roles=('MANAGER',))

    def mark_notification_read(self, actor, id):
        require_role(actor, 'MANAGER', 'ANALYST', 'ADMIN')
        return self.repository.read_notification(actor.id, uuid(id))
