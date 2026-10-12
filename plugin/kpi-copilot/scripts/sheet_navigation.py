"""Saved period views keep the same editable registers useful as history grows."""
import hashlib


def view_id(tab, period):
    return int(hashlib.sha256(('kpi:'+tab+'|'+period).encode()).hexdigest()[:7],16)


def resolve(value, ids=None):
    if not isinstance(value,str) or not value.startswith('kpi-view:'):return value
    tab,period=value[len('kpi-view:'):].split('|',1)
    if ids is None:return "#'"+tab.replace("'","''")+"'!A1"
    return f'#gid={ids[tab]}&fvid={view_id(tab,period)}'


def configure(tabs,periods,ctx):
    if (ctx.get('profile',{}).get('output') or {}).get('layout')!='simple':return
    by={t.name:t for t in tabs};labels=[p['name'] for p in periods]
    colors=['EAF1F8','EFF4EA','F1EDF7','F8F1E7']
    for name in ('KPI Summary','Team Review','Capacity','Task Register','Defect Register','Open Questions'):
        t=by.get(name)
        if not t or not t.filter_range:continue
        col=2 if name in ('Task Register','Defect Register','Open Questions') else 1
        # Registers contain a row number before Period.
        if name in ('Task Register','Defect Register'):
            cols=(t.readback or {}).get('cols') or []
            col=next((i for i,c in enumerate(cols,1) if c[0]=='period'),col)
        for i,p in enumerate(labels):
            criteria={str(col-1):{'condition':{'type':'TEXT_EQ','values':[{'userEnteredValue':p}]}}}
            if name=='Open Questions':criteria['5']={'condition':{'type':'CUSTOM_FORMULA','values':[{'userEnteredValue':'=OR($F4="Open",$F4="Answered - to apply")'}]}}
            if name=='Team Review':criteria['10']={'condition':{'type':'CUSTOM_FORMULA','values':[{'userEnteredValue':'=OR($K4="Open",$K4="Stale")'}]}}
            t.filter_views.append({'filterViewId':view_id(name,p),'title':'KPI · '+p,
                                   'criteria':criteria})
            r1,_,r2,_=t.filter_range
            t.when(r1+1,col,r2,col,f'=${__import__("sheet_model").col(col)}{r1+1}="{p}"',fill=colors[i%len(colors)])
        if name=='Open Questions':
            t.filter_views.append({'filterViewId':view_id(name,'active'),'title':'KPI · Active questions',
                                   'criteria':{'5':{'condition':{'type':'CUSTOM_FORMULA','values':[{'userEnteredValue':'=OR($F4="Open",$F4="Answered - to apply")'}]}}}})
        if name=='Team Review':
            t.filter_views.append({'filterViewId':view_id(name,'active'),'title':'KPI · Pending review',
                                   'criteria':{'10':{'condition':{'type':'CUSTOM_FORMULA','values':[{'userEnteredValue':'=OR($K4="Open",$K4="Stale")'}]}}}})
    import sheet_model as M
    nav=M.Tab('Period Navigation');nav.hidden=True;tabs.append(nav)
    d=by['Dashboard']
    for row,p in enumerate(labels,2):
        nav.put(row,9,p,'data')
        for c,name in enumerate(('Team Review','Open Questions','Capacity','KPI Summary'),10):
            if name in by:nav.put(row,c,'kpi-view:'+name+'|'+p,'data')
    for row,name,c in ((24,'Review this period',10),(25,'Answer questions',11),(26,'People and project hours',12),(27,'Calculation and notes',13)):
        letter=__import__('sheet_model').col(c)
        d.put(row,1,name,'link',f=f'=IFERROR(HYPERLINK(INDEX(\'Period Navigation\'!${letter}$2:${letter}${max(2,len(labels)+1)},MATCH($B$4,\'Period Navigation\'!$I$2:$I${max(2,len(labels)+1)},0)),"{name}"),"")')
    d.put(28,1,'All pending questions','link',link='kpi-view:Open Questions|active')
    d.put(29,1,'All pending team checks','link',link='kpi-view:Team Review|active')
