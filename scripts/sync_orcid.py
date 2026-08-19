import html,re,urllib.parse,urllib.request,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/"articulos"; ORCID="0000-0003-0553-6210"
def getj(u):
    q=urllib.request.Request(u,headers={"Accept":"application/vnd.orcid+json","User-Agent":"Nutreconciencia/1.0"})
    with urllib.request.urlopen(q,timeout=60) as r:return json.loads(r.read().decode())
def val(x): return x.get("value","") if isinstance(x,dict) else (x or "")
def slug(s): return re.sub(r"[^a-zA-Z0-9]+","-",s.lower()).strip("-")[:90] or "paper"
page=0; groups=[]
while True:
    d=getj("https://pub.orcid.org/v3.0/"+ORCID+"/works?page="+str(page)+"&page-size=100")
    c=d.get("group",[])
    if not c:break
    groups+=c
    if len(c)<100:break
    page+=1
seen=set()
for g in groups:
    s=(g.get("work-summary") or [{}])[0]
    title=val(s.get("title",{}).get("title"))
    if not title:continue
    ext=s.get("external-ids",{}).get("external-id",[])
    doi=""
    for e in ext:
        if (e.get("external-id-type") or "").lower()=="doi":doi=val(e.get("external-id-value"));break
    key=(doi or title).lower()
    if key in seen:continue
    seen.add(key)
    year=val((s.get("publication-date") or {}).get("year"));journal=val(s.get("journal-title"));sl=slug(title)
    d=ART/sl;d.mkdir(exist_ok=True)
    subject=urllib.parse.quote("Solicitud de estudio completo — "+title)
    (d/"orcid.json").write_text(json.dumps({"title":title,"year":year,"journal":journal,"doi":doi,"orcid":ORCID},ensure_ascii=False,indent=2))
    pagehtml="<html lang='es'><head><meta charset='utf-8'><title>"+html.escape(title)+" | Miguel López Moreno</title><link rel='stylesheet' href='../../assets/styles.css'></head><body><main><section class='study-hero'><div class='kicker'>"+html.escape(journal)+" · "+html.escape(year)+"</div><h1 class='study-title-original'>"+html.escape(title)+"</h1></section><section class='study-layout'><article class='study-main'><p class='study-summary'>Ficha incorporada desde ORCID. El resumen en castellano se completará con el abstract de PubMed/Crossref cuando esté disponible.</p><div class='study-request'><strong>¿Quieres consultar el estudio completo?</strong><a href='mailto:miguel@nutreconciencia.com?subject="+subject+"'>Solicitar el estudio completo por email</a></div></article></section></main></body></html>"
    (d/"index.html").write_text(pagehtml,encoding="utf-8")
