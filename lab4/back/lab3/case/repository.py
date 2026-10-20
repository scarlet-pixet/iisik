from back.lab3.common import Repository, model
from .models import Case, Comment, Decision, Report, Notification

class CaseRepository(Repository):
    def enrich(self,rows):
        ids=[r['id'] for r in rows]
        comments=self.db.query('SELECT * FROM case_comments WHERE case_id=ANY(%s::uuid[]) ORDER BY created_at,id',(ids,)) if ids else []
        decisions=self.db.query('SELECT * FROM case_decisions WHERE case_id=ANY(%s::uuid[]) ORDER BY review_cycle,id',(ids,)) if ids else []
        return [model(Case,r,comments=[model(Comment,x) for x in comments if x['case_id']==r['id']],decisions=[model(Decision,x) for x in decisions if x['case_id']==r['id']]) for r in rows]
    def case(self,id):
        rows=self.db.query('SELECT * FROM review_cases WHERE id=%s',(id,))
        return self.enrich(rows)[0] if rows else None
    def cases(self,filters,page):
        clauses,params=[],[]
        for key,col in [('status','status'),('priority','priority'),('assigneeId','assignee_id'),('clientId','client_id')]:
            if key in filters:clauses.append(col+'=%s');params.append(filters[key])
        if 'period' in filters:clauses.extend(['created_at>=%s','created_at<%s']);params.extend(filters['period'])
        rows,total=self.page_rows('SELECT * FROM review_cases',clauses,params,page)
        return self.enrich(rows),total
    def report(self,id):return model(Report,self.db.one('SELECT * FROM reports WHERE id=%s',(id,)))
    def notifications(self,recipient,unread,page):
        clauses=['recipient_id=%s'];params=[recipient]
        if unread:clauses.append('read_at IS NULL')
        rows,total=self.page_rows('SELECT * FROM notifications',clauses,params,page)
        return [model(Notification,r) for r in rows],total
