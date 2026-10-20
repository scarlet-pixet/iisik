from back.lab3.common import Repository, model
from .models import User

class AuthRepository(Repository):
    def by_id(self, id):
        return model(User, self.db.one('SELECT u.id,u.login,u.is_active,r.code AS role FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=%s', (id,)))
