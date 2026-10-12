"""Client-neutral status envelopes and explicitly requested notification delivery."""
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from pathlib import Path


def email_ready(config):
    email=config.get('email') or {}
    return bool(email.get('to') and email.get('from') and
                (email.get('route')=='host_gmail' or email.get('smtp_host')))


def questions(config):
    rows=[]
    if 'email' in config.get('channels',[]) and not email_ready(config):
        rows.append({'id':'notification:email','about':'Scheduled notifications','question':'Email status delivery needs configured recipients, sender and SMTP connection in the private profile. Host notifications remain available. Do not put credentials in chat.', 'blocking':False})
    if 'webhook' in config.get('channels',[]) and not config.get('webhook',{}).get('url_env'):
        rows.append({'id':'notification:webhook','about':'Scheduled notifications','question':'Configure a supported private webhook provider and destination recipients for phone or other host notifications.', 'blocking':False})
    return rows


def prepare(ws,results,questions,destination,mode):
    cfg=(ws.profile.get('output') or {}).get('notifications') or {'channels':['host']}
    active=[q for q in questions if q['status'] in ('Open','Answered - to apply')]
    body=[f'KPI review: {ws.name}',f'Sheet: {destination.get("url") or destination.get("path")}',f'Mode: {mode}. PMS submission requires approval.']
    periods=results['periods']
    import reporting
    cadence=(ws.profile.get('periods') or {}).get('cadence')
    if cadence:
        windows=reporting.windows(cadence,ws.today)
        candidates=[p['name'] for p in windows if not p.get('upcoming') and (mode!='unattended' or p['end']<=ws.today)]
        selected=candidates[-1] if candidates else None
        periods=[p for p in periods if p['period']==selected]
    for p in periods:
        body.append('\n'+p['period'])
        for m in p['measures']:
            value=(m.get('availability') or 'Not measured') if m['value'] is None else f'{m["value"]:g} {m["unit"]}'
            body.append(f'{m["name"]}: {value}'+(' (provisional)' if m.get('availability')=='Provisional' and m['value'] is not None else '')+'.')
    if active:
        body.append(f'\n{len(active)} questions or reviews are still open. Dashboard opens the selected period’s Team Review and Open Questions; both contain the details and source links.')
        focused=[q for q in active if q.get('about') in {p['period'] for p in periods} and not q['id'].startswith('team-review:')]
        body.extend('- '+q['question'].split('\n')[0][:180]+('… See the Sheet for details.' if len(q['question'])>180 else '') for q in focused[:3])
    doc={'generated_at':__import__('board').now_iso(),'project':ws.pid,'run_mode':mode,
         'status':'needs_review' if active else 'ready_for_review','sheet':destination.get('url'),
         'periods':[p['period'] for p in results['periods']], 'questions':active,
         'channels':cfg.get('channels',['host']),'subject':f'KPI review · {ws.name} · {ws.today}',
         'body':'\n'.join(body),'assistant_host':cfg.get('host','current'),'delivery':{}}
    for channel in doc['channels']:
        ready=channel=='host' or channel=='email' and email_ready(cfg) or channel=='webhook' and bool(cfg.get('webhook',{}).get('url_env'))
        doc['delivery'][channel]='prepared' if ready else 'configuration_required'
    path=ws.dir/'status.json';path.write_text(json.dumps(doc,indent=2));path.chmod(0o600)
    (ws.dir/'status.md').write_text(doc['body'])
    return doc


def send(status_path,config,apply=False):
    doc=json.loads(Path(status_path).read_text());sent={}
    for channel in config.get('channels',['host']):
        if channel=='host':sent[channel]='available to '+config.get('host','current assistant host');continue
        if channel=='email':
            c=config.get('email') or {};recipients=c.get('to') or []
            if not recipients:raise ValueError('Configure output.notifications.email.to before sending email')
            if not apply:sent[channel]={'to':recipients,'subject':doc['subject'],'route':c.get('route','smtp'),'dry_run':True};continue
            if c.get('route')=='host_gmail':
                raise ValueError('Use the authenticated assistant-host Gmail connector to send this prepared status; the CLI does not own that connection')
            msg=EmailMessage();msg['Subject']=doc['subject'];msg['From']=c['from'];msg['To']=', '.join(recipients);msg.set_content(doc['body'])
            with smtplib.SMTP(c['smtp_host'],int(c.get('smtp_port',587)),timeout=30) as smtp:
                smtp.starttls()
                if c.get('username_env'):smtp.login(os.environ[c['username_env']],os.environ[c['password_env']])
                smtp.send_message(msg)
            sent[channel]='sent'
        elif channel=='webhook':
            c=config.get('webhook') or {};endpoint=os.environ.get(c.get('url_env',''))
            if not endpoint:raise ValueError('Configure a private webhook URL environment variable')
            if not endpoint.startswith('https://'):raise ValueError('Notification webhooks require HTTPS')
            if not apply:sent[channel]={'provider':c.get('provider'),'recipients':c.get('recipients',[]),'dry_run':True};continue
            payload={'subject':doc['subject'],'text':doc['body'],'recipients':c.get('recipients',[])}
            req=urllib.request.Request(endpoint,json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=30) as response:
                if response.status not in range(200,300):raise ValueError('Notification delivery failed')
            sent[channel]='sent'
        else:raise ValueError('Unsupported notification channel: '+channel)
    if apply:
        doc['delivery'].update(sent);Path(status_path).write_text(json.dumps(doc,indent=2))
    return sent
