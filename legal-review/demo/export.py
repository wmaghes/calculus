import os, sys, json, shutil, pyotp, httpx
from pathlib import Path
sys.path.insert(0, "/home/user/calculus/legal-review/tests")
from legal_fixtures import Legal
OUT=Path(sys.argv[1]); D=OUT/"data"; shutil.rmtree(D, ignore_errors=True)
os.environ["LEXREVIEW_DATA_ROOT"]=str(D)
from lexreview.config import load_settings
from lexreview.app import App
from lexreview.authz import Perm, Role
from lexreview.legal.gateway import LegalGateway
from lexreview.qa import looks_like_injection
a=App.initialize(load_settings()); uid,t=a.bootstrap_admin("admin","admin-password-123")
p=a.principal(a.login("admin","admin-password-123",pyotp.TOTP(t).now()))
c=a.create_case(p,"Harbor Point v. Meridian (synthetic)"); a.add_member(p,c,uid,Role.CASE_ADMIN)
a.ingest(a.authorize(p,c,Perm.INGEST), Path(os.environ["LEXREVIEW_APPROVED_DATA_DIR"])/"docs")
ctx=a.authorize(p,c,Perm.MANAGE); st=a.store(ctx)
docs={d["source_name"]:d for d in st.list_documents(ctx)}
a.set_restriction(ctx, docs["docs/contracts/amendment_1.docx"]["doc_id"], "aeo")
a.grant_label(p,c,uid,"aeo"); ctx=a.authorize(p,c,Perm.SEARCH)
conn=st.conn
out={"case":{"name":"Harbor Point Cold Storage v. Meridian Freightways (fictional)","id":c}}
out["docs"]=[dict(zip(("doc_id","parent_id","source_name","kind","status","reason","page_count","ocr_pages","low_conf_pages","restriction"),r))
  for r in conn.execute("SELECT doc_id,parent_id,source_name,kind,status,reason,page_count,ocr_pages,low_conf_pages,restriction FROM documents ORDER BY source_name")]
pages={}
for d,pn,loc,text,ocr,conf in conn.execute("SELECT doc_id,page_no,locator,text,ocr,ocr_conf FROM pages ORDER BY doc_id,page_no"):
    pages.setdefault(d,[]).append([pn,loc,text,ocr,conf])
out["pages"]=pages
out["chunks"]=conn.execute("SELECT doc_id,page_no,char_start,char_end FROM chunks ORDER BY chunk_id").fetchall()
for d in out["docs"]:
    d["injection"]=any(looks_like_injection(pg[2]) for pg in pages.get(d["doc_id"],[]))
ents=[dict(zip(("id","kind","name"),r)) for r in conn.execute("SELECT entity_id,kind,name FROM entities")]
for e in ents:
    e["mentions"]=conn.execute("SELECT doc_id,count(*) FROM mentions WHERE entity_id=? GROUP BY doc_id",(e["id"],)).fetchall()
out["entities"]=ents
tl=a.timeline(ctx, include_rows=True)
ev_ents={}
for eid,ent in conn.execute("SELECT event_id,entity_id FROM event_entities"): ev_ents.setdefault(eid,[]).append(ent)
out["events"]=[{k:e[k] for k in ("event_id","date","date_start","date_end","precision","date_text","flags","tags","source","doc_id","page_no","char_start","char_end")}|{"ents":ev_ents.get(e["event_id"],[])} for e in tl["events"]]
out["unplaced"]=[{k:u[k] for k in ("doc_id","page_no","date_text","reason")} for u in tl["unplaced"]]
a.legal_gateway=LegalGateway(transport=httpx.MockTransport(Legal()), enabled=True)
q=a.legal_propose(ctx,"carrier liability for temperature-controlled cargo damage",["courtlistener","ohio_code","mi_code","ecfr"],["ohio","michigan","federal"])
a.legal_decide(ctx,q["query_id"],True); r=a.legal_run(ctx,q["query_id"])
out["fixture_leads"]={"status":r["source_status"],"leads":r["leads"]}
out["labels"]=json.load(open(Path(os.environ["LEXREVIEW_APPROVED_DATA_DIR"])/"LABELS.json"))["topics"]
s=json.dumps(out,separators=(",",":"))
(OUT/"data.json").write_text(s); print("bytes",len(s),"docs",len(out["docs"]),"events",len(out["events"]),"chunks",len(out["chunks"]))
