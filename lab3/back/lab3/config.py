from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    databases:dict[str,str]
    actor_id:str
    transport:str='mock'
    @classmethod
    def load(cls):
        if os.getenv('LAB3_TRANSPORT','mock')!='mock':raise RuntimeError('ЛР3 допускает только mock transport')
        db={svc:os.getenv('LAB3_'+svc.upper()+'_DSN',f'postgresql://bank_{svc}_reader:lab3_read_only@127.0.0.1:{56431+i}/bank_{svc}') for i,svc in enumerate(['auth','transaction','analysis','case'])}
        return cls(db,os.getenv('LAB3_DEMO_ACTOR','43817961-b437-5313-9754-19535c80b1b9'))
