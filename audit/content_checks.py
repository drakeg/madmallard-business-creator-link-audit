"""Conservative, bounded HTML evidence. Never executes scripts or follows metadata URLs."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin

def asin(url):
    try: p=urlsplit(url)
    except ValueError: return ""
    if p.hostname!="amazon.com" and not (p.hostname or "").endswith(".amazon.com"): return ""
    match=re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)",p.path,re.I)
    return match.group(1).upper() if match else ""

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.title="";self.canonical="";self.og_url="";self.og_type="";self.main_asin="";self.products=[]
        self.in_title=False;self.script_type="";self.script="";self.hidden=0;self.visible=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="title":self.in_title=True
        if tag in ("script","style"):self.hidden+=1
        if tag=="script":self.script_type=a.get("type","");self.script=""
        if tag=="link" and "canonical" in a.get("rel","").split():self.canonical=a.get("href","")[:2000]
        if tag=="meta":
            prop=a.get("property",a.get("name","")).lower()
            if prop=="og:url":self.og_url=a.get("content","")[:2000]
            if prop=="og:type":self.og_type=a.get("content","").lower()
        if tag=="input" and (a.get("id","").upper()=="ASIN" or a.get("name","").upper()=="ASIN"):
            self.main_asin=a.get("value","").upper()
    def handle_data(self,data):
        if self.in_title:self.title=(self.title+data)[:400]
        if self.script_type=="application/ld+json" and self.hidden:self.script=(self.script+data)[:64000]
        if not self.hidden and len(self.visible)<2000:self.visible.append(data[:1000])
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
        if tag=="script":
            if self.script_type=="application/ld+json":
                try:self.collect(json.loads(self.script))
                except (ValueError,TypeError):pass
            self.script_type="";self.script=""
        if tag in ("script","style"):self.hidden=max(0,self.hidden-1)
    def collect(self,value,depth=0):
        if depth>8:return
        if isinstance(value,list):
            for x in value[:100]:self.collect(x,depth+1)
        elif isinstance(value,dict):
            types=value.get("@type",[])
            if isinstance(types,str):types=[types]
            if not isinstance(types,list):types=[]
            if "Product" in types:self.products.append(value)
            if "@graph" in value:self.collect(value["@graph"],depth+1)

def inspect_content(original,final,body):
    evidence={"outcome":"unavailable","title":"","canonical":"","reasons":[],"expected_asin":asin(original) or asin(final)}
    if not body:
        evidence["reasons"]=["No inspectable HTML was retrieved."];return evidence
    page=Page()
    try:page.feed(body.decode("utf-8",errors="replace"))
    except (AssertionError,ValueError):
        evidence["reasons"].append("HTML parsing was partial.")
    title=page.title.strip();text=" ".join(page.visible).lower()
    try: canonical=urljoin(final,page.canonical or page.og_url) if (page.canonical or page.og_url) else ""
    except ValueError: canonical=""
    try: canonical_parts=urlsplit(canonical)
    except ValueError: canonical="";canonical_parts=urlsplit("")
    evidence.update(title=title,canonical=canonical)
    if re.search(r"robot check|access denied|security verification|verify.*human|captcha",title,re.I) or any(x in text for x in ["enter the characters you see below","verify you are human","automated access to amazon"]):
        evidence.update(outcome="bot_protection",reasons=["The returned page asks for robot/security verification."]);return evidence
    if re.search(r"page not found|product not found|404 not found|page unavailable",title,re.I):
        evidence.update(outcome="soft_missing",reasons=["The page title reports missing/unavailable content despite HTTP success."]);return evidence
    expected=evidence["expected_asin"]
    canonical=evidence["canonical"]
    final_parts=urlsplit(final)
    product_expected=bool(expected) or urlsplit(original).hostname=="amzn.to"
    if product_expected and ((canonical and urlsplit(canonical).path in ("","/") and (canonical_parts.hostname=="amazon.com" or (canonical_parts.hostname or "").endswith(".amazon.com"))) or (final_parts.hostname=="amazon.com" or (final_parts.hostname or "").endswith(".amazon.com")) and final_parts.path in ("","/")):
        evidence.update(outcome="homepage",reasons=["A product-oriented link returned or declared an Amazon homepage, not a product page."]);return evidence
    matched=bool(expected and page.main_asin==expected)
    if expected:
        for product in page.products:
            identifiers=[str(product.get(k,"")).upper() for k in ("sku","productID","mpn")]
            if expected in identifiers or asin(str(product.get("url","")))==expected:matched=True
        if asin(canonical)==expected and page.og_type in ("product","product.item"):matched=True
    if matched:
        evidence.update(outcome="product_match",reasons=["The main product identifier on the page matches the product identifier in the checked URL. This does not prove the original description named the right item."]);return evidence
    if expected and (page.main_asin and page.main_asin!=expected or canonical and asin(canonical) and asin(canonical)!=expected):
        evidence.update(outcome="product_mismatch",reasons=["The page's main/canonical product identifier differs from the checked product URL."]);return evidence
    if re.fullmatch(r"sign in|log in|login",title,re.I):
        evidence.update(outcome="access_gate",reasons=["A sign-in page was returned; destination content could not be verified."]);return evidence
    evidence.update(outcome="page_reached" if title and not product_expected else "unconfirmed_product",reasons=["Page content was retrieved, but intended-product identity was not established."])
    return evidence
