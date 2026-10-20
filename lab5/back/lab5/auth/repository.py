"""Only the Auth Service has a connection to the Auth PostgreSQL database."""
from uuid import uuid4
from types import SimpleNamespace

from back.lab4.common import WritableDatabase, command
from back.lab3.common import DomainError


USER_SQL = (
    "SELECT u.id::text AS id,u.login,u.password_hash,u.is_active,"
    "r.code AS role FROM users u JOIN roles r ON r.id=u.role_id"
)


class AuthRepository:
    def __init__(self, dsn):
        self.db = WritableDatabase(dsn, "auth")

    def by_login(self, login):
        return self.db.one(USER_SQL + " WHERE u.login=%s", (login,))

    def by_id(self, user_id):
        return self.db.one(USER_SQL + " WHERE u.id=%s", (user_id,))

    def health(self):
        return self.db.health()

    def register(self, actor, login, password_hash, role, key, password_digest):
        payload = {"login": login, "roleCode": role, "passwordDigest": password_digest}

        def perform(conn):
            role_row = conn.execute("SELECT id FROM roles WHERE code=%s", (role,)).fetchone()
            if role_row is None:
                raise DomainError("BAD_INPUT", "Роль не найдена")
            user_id = str(uuid4())
            conn.execute(
                "INSERT INTO users(id,role_id,login,password_hash,is_active,created_at) "
                "VALUES (%s,%s,%s,%s,true,now())",
                (user_id, role_row["id"], login, password_hash),
            )
            return user_id

        with self.db.connect() as conn:
            user_id = command(conn, actor=SimpleNamespace(id=actor["id"]), name="registerStaff", key=key,
                              payload=payload, perform=perform)
        return self.by_id(user_id)

    def block(self, actor, user_id, key):
        def perform(conn):
            row = conn.execute("SELECT id,is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
            if row is None:
                raise DomainError("NOT_FOUND", "Сотрудник не найден")
            if not row["is_active"]:
                raise DomainError("CONFLICT", "Сотрудник уже заблокирован")
            conn.execute("UPDATE users SET is_active=false,disabled_at=now() WHERE id=%s", (user_id,))
            return user_id

        with self.db.connect() as conn:
            result = command(conn, actor=SimpleNamespace(id=actor["id"]), name="blockStaff", key=key,
                             payload={"userId": user_id}, perform=perform)
        return self.by_id(result)

    def change_role(self, actor, user_id, role, key):
        def perform(conn):
            row = conn.execute("SELECT id,is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
            if row is None:
                raise DomainError("NOT_FOUND", "Сотрудник не найден")
            if not row["is_active"]:
                raise DomainError("CONFLICT", "Заблокированному сотруднику нельзя менять роль")
            role_row = conn.execute("SELECT id FROM roles WHERE code=%s", (role,)).fetchone()
            if role_row is None:
                raise DomainError("BAD_INPUT", "Роль не найдена")
            conn.execute("UPDATE users SET role_id=%s WHERE id=%s", (role_row["id"], user_id))
            return user_id

        with self.db.connect() as conn:
            result = command(conn, actor=SimpleNamespace(id=actor["id"]), name="changeStaffRole", key=key,
                             payload={"userId": user_id, "roleCode": role}, perform=perform)
        return self.by_id(result)
