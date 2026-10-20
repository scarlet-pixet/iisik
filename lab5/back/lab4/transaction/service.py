from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from back.lab3.common import DomainError, currency, money, period, uuid
from back.lab3.transaction.service import TransactionService as ReadService
from back.lab4.common import require_role, required_text


class TransactionService(ReadService):
    def create_client(self, actor, input):
        require_role(actor, 'MANAGER', 'ADMIN')
        external = required_text(input['externalId'], 'externalId', 64)
        display = required_text(input['displayName'], 'displayName', 160)
        segment = input.get('segment')
        if segment is not None: segment = required_text(segment, 'segment', 50)
        payload = {'externalId': external, 'displayName': display, 'segment': segment}

        def perform(conn):
            value = str(uuid4())
            conn.execute('INSERT INTO bank_clients(id,external_id,display_name,segment,is_active) VALUES (%s,%s,%s,%s,true)',
                         (value, external, display, segment))
            return value

        result = self.repository.execute(actor, 'createClient', input['idempotencyKey'], payload, perform)
        return self.repository.client(result)

    def open_account(self, actor, input):
        require_role(actor, 'MANAGER', 'ADMIN')
        client_id = uuid(input['clientId'])
        external = required_text(input['externalId'], 'externalId', 64)
        code = currency(input['currency'])
        payload = {'clientId': client_id, 'externalId': external, 'currency': code}

        def perform(conn):
            client = conn.execute('SELECT is_active FROM bank_clients WHERE id=%s', (client_id,)).fetchone()
            if not client: raise DomainError('NOT_FOUND', 'Клиент не найден')
            if not client['is_active']: raise DomainError('CONFLICT', 'Клиент заблокирован')
            value = str(uuid4())
            conn.execute('INSERT INTO accounts(id,client_id,external_id,currency,status) VALUES (%s,%s,%s,%s,%s)',
                         (value, client_id, external, code, 'OPEN'))
            return value

        result = self.repository.execute(actor, 'openAccount', input['idempotencyKey'], payload, perform)
        return self.repository.account(result)

    def register_counterparty(self, actor, input):
        require_role(actor, 'MANAGER', 'ADMIN')
        external = required_text(input['externalId'], 'externalId', 64)
        display = required_text(input['displayName'], 'displayName', 160)
        category = input.get('category')
        if category is not None: category = required_text(category, 'category', 50)
        payload = {'externalId': external, 'displayName': display, 'category': category}

        def perform(conn):
            value = str(uuid4())
            conn.execute('INSERT INTO counterparties(id,external_id,display_name,category) VALUES (%s,%s,%s,%s)',
                         (value, external, display, category))
            return value

        result = self.repository.execute(actor, 'registerCounterparty', input['idempotencyKey'], payload, perform)
        return self.repository.counterparty(result)

    def register_transaction(self, actor, input):
        require_role(actor, 'MANAGER', 'ANALYST')
        account_id = uuid(input['accountId'])
        counterparty_id = uuid(input['counterpartyId']) if input.get('counterpartyId') else None
        source = required_text(input['source'], 'source', 32)
        external = required_text(input['externalId'], 'externalId', 100)
        code = currency(input['currency'])
        direction = input['direction']
        if direction not in ('IN', 'OUT'): raise DomainError('BAD_INPUT', 'Некорректное направление')
        try:
            amount = Decimal(str(input['amount']))
            if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal('9999999999999999.99'):
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise DomainError('BAD_INPUT', 'Сумма должна быть положительной с точностью до копеек') from None
        occurred = input['occurredAt']
        if isinstance(occurred, str):
            try: occurred = datetime.fromisoformat(occurred.replace('Z', '+00:00'))
            except ValueError: raise DomainError('BAD_INPUT', 'Некорректная дата операции') from None
        if not occurred.tzinfo: raise DomainError('BAD_INPUT', 'Дата операции требует часовой пояс')
        payload = {'source':source,'externalId':external,'accountId':account_id,'counterpartyId':counterparty_id,
                   'amount':str(amount),'currency':code,'direction':direction,'occurredAt':occurred.isoformat()}

        def perform(conn):
            account = conn.execute('SELECT a.currency,a.status,c.is_active FROM accounts a JOIN bank_clients c ON c.id=a.client_id WHERE a.id=%s',
                                   (account_id,)).fetchone()
            if not account: raise DomainError('NOT_FOUND', 'Счёт не найден')
            if account['status'] != 'OPEN' or not account['is_active']:
                raise DomainError('CONFLICT', 'Счёт или клиент недоступен')
            if account['currency'] != code: raise DomainError('BAD_INPUT', 'Валюта операции не совпадает с валютой счёта')
            if counterparty_id and not conn.execute('SELECT 1 FROM counterparties WHERE id=%s', (counterparty_id,)).fetchone():
                raise DomainError('NOT_FOUND', 'Контрагент не найден')
            value = str(uuid4())
            conn.execute('INSERT INTO transactions '
                         '(id,source,external_id,account_id,counterparty_id,batch_id,amount,currency,direction,occurred_at,ingested_at) '
                         'VALUES (%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,now())',
                         (value, source, external, account_id, counterparty_id, amount, code, direction, occurred))
            return value

        result = self.repository.execute(actor, 'registerTransaction', input['idempotencyKey'], payload, perform)
        return self.repository.transaction(result)

    def transaction_summary(self, filter=None):
        filters = dict(filter or {})
        if 'clientId' in filters: filters['clientId'] = uuid(filters['clientId'])
        if 'currency' in filters: filters['currency'] = currency(filters['currency'])
        if 'period' in filters: filters['period'] = period(filters['period'])
        if 'direction' in filters and filters['direction'] not in ('IN', 'OUT'):
            raise DomainError('BAD_INPUT', 'Неизвестное направление')
        for key in ('amountFrom', 'amountTo'):
            if key in filters: filters[key] = money(filters[key])
        if 'amountFrom' in filters and 'amountTo' in filters and filters['amountFrom'] > filters['amountTo']:
            raise DomainError('BAD_INPUT', 'amountFrom > amountTo')
        return self.repository.summary(filters)
