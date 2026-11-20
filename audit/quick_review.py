"""Group exact original+tested URLs; never merge links by stripped affiliate IDs."""
import hashlib
import json
import re
from collections import Counter
from .content_checks import asin
from .presentation import explain

def group_key(result):
    return hashlib.sha256(json.dumps([result.link.url,result.tested_url],ensure_ascii=True).encode()).hexdigest()

def label_matches(title,label):
    words=set(re.findall(r"[a-z0-9]{3,}",label.lower()))-{"the","and","for","with","our","gear","use","link","amazon","https","www","com"}
    if len(words)<2:return False
    matches=len(words.intersection(set(re.findall(r"[a-z0-9]{3,}",title.lower()))))
    return matches>=min(3,len(words)) and matches/len(words)>=0.5

def assessment(result,labels):
    ev=result.content_evidence or {}; outcome=ev.get("outcome","")
    if result.manual_status=="wrong_destination":
        return "attention","Wrong destination reported","An owner/manual report needs correction review.",0
    if result.category=="broken" and result.status in (404,410):
        return "attention","Missing page","HTTP confirms a missing/gone resource.",0
    if outcome in ("homepage","soft_missing","product_mismatch","product_changed"):
        return "attention","Destination problem suspected"," ".join(ev.get("reasons",[])),1
    if result.status is None or result.status in (401,403,429) or result.status>=500 or outcome in ("bot_protection","access_gate"):
        return "inconclusive","Blocked or inconclusive"," ".join(ev.get("reasons",[])) or result.reason,2
    if outcome=="product_match" and labels and all(label_matches(ev.get("title",""),label) for label in labels):
        return "likely_valid","Likely correct product page","Main product identifier and description-label words match the returned page. Commission/discount tracking is not verified.",3
    if result.manual_status=="destination_verified":
        return "reviewed","Destination checked manually","A manual destination review is recorded; commission tracking remains unverified.",4
    if outcome=="page_reached":
        return "reachable","Page reached","Content was returned with no detected missing-page signal. Intended product/owner identity is not proven.",3
    if outcome=="product_match":
        return "review","Product page found — label needs confirmation","The product ID matches the URL, but the description's intended item has not been matched confidently.",2
    return "review","Content not verified","Inspect page content first, or review this unique link once. HTTP success alone does not prove the destination.",2

def grouped_results(scan):
    sources={s.pk:s for s in scan.project.sources.all()}
    grouped={}
    for r in scan.results.select_related("link__source").defer("link__source__content").order_by("pk"):
        key=group_key(r)
        group=grouped.setdefault(key,{"key":key,"rows":[],"labels":[]})
        group["rows"].append(r)
        source=sources.get(r.link.source_id)
        if source:
            line=next((x for x in source.content.splitlines() if r.link.url in x),"")
            label=line.split(r.link.url,1)[0].strip(" :-")
            if label and label not in group["labels"]:group["labels"].append(label[:300])
    for group in grouped.values():
        decisions=[(assessment(r,group["labels"]),r) for r in group["rows"]]
        decisions.sort(key=lambda pair:pair[0][3])
        (bucket,headline,detail,priority),representative=decisions[0]
        statuses={r.manual_status for r in group["rows"] if r.manual_status!="unreviewed"}
        if len(statuses)>1:
            bucket,headline,detail,priority="attention","Conflicting manual decisions","Review the source records before applying one shared decision.",0
        group.update(bucket=bucket,headline=headline,detail=detail,priority=priority,representative=representative,count=len(group["rows"]),explanation=explain(representative),evidence=representative.content_evidence)
    return sorted(grouped.values(),key=lambda g:(g["priority"],g["key"]))

def state_digest(group):
    digest=hashlib.sha256()
    for r in group["rows"]:
        values=[r.pk,r.manual_status,r.notes,r.replacement,str(r.reviewed_at),r.link.manual_status,r.link.notes,r.link.replacement,str(r.link.reviewed_at)]
        digest.update(json.dumps(values,ensure_ascii=True).encode())
    return digest.hexdigest()
