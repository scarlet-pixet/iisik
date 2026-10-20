from back.lab3.common import Repository, model
from .models import Profile, Result, Run, RuleVersion, RuleHit

class AnalysisRepository(Repository):
    def profile(self,id): return model(Profile,self.db.one('SELECT * FROM behavior_profiles WHERE id=%s',(id,)))
    def run(self,id): return model(Run,self.db.one('SELECT * FROM analysis_runs WHERE id=%s',(id,)))
    def result(self,id):
        row=self.db.one('SELECT * FROM analysis_results WHERE id=%s',(id,))
        if not row:return None
        hits=self.db.query('SELECT h.*,r.code AS rule_code,v.version FROM rule_hits h JOIN rule_versions v ON v.id=h.rule_version_id JOIN analysis_rules r ON r.id=v.rule_id WHERE h.result_id=%s ORDER BY r.code',(id,))
        return model(Result,row,hits=[model(RuleHit,x) for x in hits])
    def rule_versions(self,id):return [model(RuleVersion,r) for r in self.db.query('SELECT * FROM rule_versions WHERE rule_id=%s ORDER BY version,id',(id,))]
    def run_results(self,id):
        rows=self.db.query('SELECT * FROM analysis_results WHERE run_id=%s ORDER BY transaction_id',(id,))
        return {str(r['transaction_id']):r for r in rows}
    def hit_codes(self,run):
        rows=self.db.query('SELECT a.transaction_id,r.code FROM analysis_results a JOIN rule_hits h ON h.result_id=a.id JOIN rule_versions v ON v.id=h.rule_version_id JOIN analysis_rules r ON r.id=v.rule_id WHERE a.run_id=%s ORDER BY a.transaction_id,r.code',(run,))
        out={}
        for r in rows:out.setdefault(str(r['transaction_id']),set()).add(r['code'])
        return out
    def profiles(self,client,run,curr):
        return [model(Profile,r) for r in self.db.query('SELECT * FROM behavior_profiles WHERE client_id=%s AND run_id=%s AND currency=%s ORDER BY window_end,id',(client,run,curr))]
