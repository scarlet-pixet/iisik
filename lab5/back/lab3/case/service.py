import base64,csv,io,json
from back.lab3.common import uuid, period, pagination, paged, DomainError
from back.lab3.ports import AuthReadPort

class CaseService:
    def __init__(self,repository,auth_client:AuthReadPort):self.repository,self.auth_client=repository,auth_client
    def get_case(self,id):return self.repository.case(uuid(id))
    def search_cases(self,filter=None,page=None):
        filters=dict(filter or {})
        for key in ('clientId','assigneeId'):
            if key in filters:filters[key]=uuid(filters[key])
        if 'period' in filters:filters['period']=period(filters['period'])
        if 'status' in filters and filters['status'] not in ('NEW','ASSIGNED','IN_PROGRESS','ESCALATED','CLOSED'):raise DomainError('BAD_INPUT','Неизвестный статус')
        if 'priority' in filters and filters['priority'] not in ('LOW','MEDIUM','HIGH'):raise DomainError('BAD_INPUT','Неизвестный приоритет')
        spec=pagination(page,{'id':'id','createdAt':'created_at','latestScore':'latest_score'},'createdAt')
        rows,total=self.repository.cases(filters,spec)
        return paged(rows,total,spec,page)
    def get_report(self,id):return self.repository.report(uuid(id))
    def export_report(self,id):
        report=self.get_report(id)
        if report is None:raise DomainError('NOT_FOUND','Отчёт не найден')
        output=io.StringIO(newline='');writer=csv.writer(output)
        writer.writerow(['metric','value'])
        for key,value in sorted(report.snapshot.items()):writer.writerow([key,json.dumps(value,ensure_ascii=False)])
        return {'fileName':f'report-{report.id}.csv','mediaType':'text/csv; charset=utf-8','contentBase64':base64.b64encode(output.getvalue().encode('utf-8-sig')).decode()}
    def list_notifications(self,unreadOnly=None,page=None):
        user=self.auth_client.get_current_user()
        spec=pagination(page,{'id':'id','createdAt':'created_at'},'createdAt')
        rows,total=self.repository.notifications(user.id,bool(unreadOnly),spec)
        return paged(rows,total,spec,page)
