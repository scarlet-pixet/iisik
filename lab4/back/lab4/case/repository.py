from uuid import uuid4

from back.lab3.case.repository import CaseRepository as ReadRepository
from back.lab3.case.models import Notification
from back.lab3.common import DomainError, model
from back.lab4.common import command


class CaseRepository(ReadRepository):
    def execute(self, actor, name, key, payload, perform):
        with self.db.connect() as conn:
            return command(conn, actor=actor, name=name, key=key, payload=payload, perform=perform)

    def read_notification(self, actor_id, notification_id):
        with self.db.connect() as conn:
            row = conn.execute(
                'UPDATE notifications SET read_at=coalesce(read_at,now()) '
                'WHERE id=%s AND recipient_id=%s RETURNING *',
                (notification_id, actor_id),
            ).fetchone()
            if row is None:
                raise DomainError('NOT_FOUND', 'Уведомление не найдено у текущего сотрудника')
        return model(Notification, row)
