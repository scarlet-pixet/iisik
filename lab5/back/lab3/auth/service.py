from back.lab3.common import DomainError, uuid

class AuthService:
    def __init__(self, repository, demo_actor): self.repository, self.demo_actor = repository, demo_actor
    def get_current_user(self):
        user = self.repository.by_id(uuid(self.demo_actor))
        if not user or not user.is_active: raise DomainError('NOT_FOUND', 'Учебная учётная запись не найдена')
        return user
