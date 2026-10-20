from back.lab3.common import Repository, model
from .models import Account, Client, Transaction
TX = 'SELECT t.*,a.client_id FROM transactions t JOIN accounts a ON a.id=t.account_id'

class TransactionRepository(Repository):
    def enrich_clients(self, rows):
        ids = [r['id'] for r in rows]
        accounts = self.db.query('SELECT * FROM accounts WHERE client_id=ANY(%s::uuid[]) ORDER BY id',(ids,)) if ids else []
        return [model(Client,r,accounts=[model(Account,a) for a in accounts if a['client_id']==r['id']]) for r in rows]
    def client(self, id):
        rows = self.db.query('SELECT * FROM bank_clients WHERE id=%s',(id,))
        return self.enrich_clients(rows)[0] if rows else None
    def clients(self, filters, page):
        clauses, params = [], []
        for key,col in [('externalId','external_id'),('segment','segment'),('isActive','is_active')]:
            if key in filters: clauses.append(col+'=%s');params.append(filters[key])
        rows,total = self.page_rows('SELECT * FROM bank_clients',clauses,params,page)
        return self.enrich_clients(rows),total
    def transaction(self, id): return model(Transaction,self.db.one(TX+' WHERE t.id=%s',(id,)))
    def transactions(self, filters, page):
        clauses,params = [],[]
        for key,col in [('clientId','a.client_id'),('currency','t.currency'),('direction','t.direction')]:
            if key in filters: clauses.append(col+'=%s');params.append(filters[key])
        for key,op in [('amountFrom','>='),('amountTo','<=')]:
            if key in filters:clauses.append('t.amount'+op+'%s');params.append(filters[key])
        if 'period' in filters:
            clauses.extend(['t.occurred_at >= %s','t.occurred_at < %s']);params.extend(filters['period'])
        rows,total = self.page_rows(TX,clauses,params,page)
        return [model(Transaction,r) for r in rows],total
