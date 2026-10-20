from back.lab3.transaction.repository import TransactionRepository as ReadRepository
from back.lab3.common import model
from back.lab3.transaction.models import Account
from back.lab4.common import command


class TransactionRepository(ReadRepository):
    def execute(self, actor, name, key, payload, perform):
        with self.db.connect() as conn:
            return command(conn, actor=actor, name=name, key=key, payload=payload, perform=perform)

    def account(self, id):
        return model(Account, self.db.one('SELECT * FROM accounts WHERE id=%s', (id,)))

    def counterparty(self, id):
        row = self.db.one('SELECT id,external_id,display_name,category FROM counterparties WHERE id=%s', (id,))
        return {'id':str(row['id']),'externalId':row['external_id'],'displayName':row['display_name'],
                'category':row['category']} if row else None

    def summary(self, filters):
        clauses, params = [], []
        for key, column in [('clientId', 'a.client_id'), ('currency', 't.currency'), ('direction', 't.direction')]:
            if key in filters:
                clauses.append(column + '=%s')
                params.append(filters[key])
        for key, op in [('amountFrom', '>='), ('amountTo', '<=')]:
            if key in filters:
                clauses.append('t.amount' + op + '%s')
                params.append(filters[key])
        if 'period' in filters:
            clauses.extend(['t.occurred_at >= %s', 't.occurred_at < %s'])
            params.extend(filters['period'])
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        row = self.db.one(
            'SELECT count(*)::int AS transaction_count, '
            'coalesce(sum(t.amount),0)::numeric(20,2) AS total_amount, '
            'avg(t.amount)::numeric(20,2) AS average_amount, '
            'min(t.amount) AS minimum_amount, max(t.amount) AS maximum_amount, '
            "count(*) FILTER (WHERE t.direction='IN')::int AS incoming_count, "
            "count(*) FILTER (WHERE t.direction='OUT')::int AS outgoing_count "
            'FROM transactions t JOIN accounts a ON a.id=t.account_id' + where,
            params,
        )
        return {name:row[column] for name,column in {
            'transactionCount':'transaction_count','totalAmount':'total_amount',
            'averageAmount':'average_amount','minimumAmount':'minimum_amount',
            'maximumAmount':'maximum_amount','incomingCount':'incoming_count',
            'outgoingCount':'outgoing_count',
        }.items()}
