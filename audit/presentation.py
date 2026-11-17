"""Plain-language explanations derived only from saved HTTP evidence."""
import re
from urllib.parse import urlsplit

STATUS_MEANINGS = {
    200: "OK — the server returned a successful response",
    301: "Permanent redirect — forwarded to another URL",
    302: "Temporary redirect — forwarded to another URL",
    303: "Redirect — forwarded to another URL",
    307: "Temporary redirect — forwarded to another URL",
    308: "Permanent redirect — forwarded to another URL",
    401: "Authentication required",
    403: "Access denied — may be bot protection",
    404: "Not found",
    410: "Gone",
    429: "Too many requests — rate limited",
}

def affiliate_query(url):
    try: query=urlsplit(url).query
    except ValueError: return ""
    return "&".join(part for part in query.split("&") if
        re.match(r"^(tag|ref_?|aff.*|affiliate.*|associate.*|partner.*|tracking.*|utm_.*|subid.*|clickid.*|irclickid|ascsubtag|linkcode|linkid)$",part.split("=",1)[0],re.I))

def explain(result,include_source=False):
    chain=result.chain or []
    redirects=[hop for hop in chain if hop.get("status") in (301,302,303,307,308) and hop.get("location")]
    status=result.status
    successful=status is not None and 200<=status<300
    if successful:
        headline="Destination responded — verify the product"
        assessment="No HTTP failure detected at check time."
        action="Open the final destination and confirm it is the intended product or page. Record that manual check. HTTP success does not prove availability, discount validity or commission tracking."
        tone="destination_review"
    elif result.category=="broken" and status in (404,410):
        headline="Missing page — replacement review needed"
        assessment="The final server returned a missing/gone response."
        action="Confirm in a browser, then propose a replacement or remove the outdated reference only after the owner approves."
        tone="broken"
    elif result.category=="unsafe_blocked":
        headline="Destination blocked by the safety rules"
        assessment="The checker refused an unsafe destination; this is not a broken-link verdict."
        action="Inspect the recorded URL and redirect target. Do not bypass the private-network or protocol protections."
        tone="unsafe_blocked"
    else:
        headline="Check inconclusive — manual follow-up needed"
        assessment="A timeout, access restriction, rate limit or other response prevented a conclusive check."
        action="Review the specific failure below. For access restrictions, check normally in your browser; for temporary errors, retry later. Do not replace a link solely because this check was blocked."
        tone=result.category
    # A redirect landing on a site root is not evidence of the expected product.
    # This is a review hint only: do not mutate the HTTP evidence or claim a broken link.
    if successful and redirects and not getattr(result, 'manual_status', '') == 'wrong_destination':
        try:
            landing=urlsplit(result.final_url or '')
            original=urlsplit(result.link.url)
            generic_root=(landing.scheme in ('http','https') and bool(landing.hostname)
                          and landing.path in ('','/') and not landing.query and not landing.fragment
                          and (landing.hostname.lower().rstrip('.') != (original.hostname or '').lower().rstrip('.')))
        except ValueError:
            generic_root=False
        if generic_root:
            headline="Generic homepage reached — check intended product"
            assessment="The link redirected to a site's homepage, not a specific product path. This may be intentional, but needs confirmation."
            action="Open the final homepage and check against the product or page described in the source. Verify any affiliate attribution separately. Do not replace the link without owner approval."
            tone="http_review"
    if getattr(result,'manual_status','') == 'wrong_destination':
        headline="Wrong destination reported — correction review needed"
        assessment="The HTTP request received a response, but a manual check reported the wrong page or product."
        action="Compare the original shortlink with the recorded HTTP product URL in your browser. Confirm the intended product and an appropriate affiliate URL before proposing a replacement. Do not treat automated HTTP success as approval."
        tone="http_review"
    if redirects:
        redirect_text=f"{len(redirects)} redirect(s) followed. A redirect is not itself a broken link; the final response determines the HTTP outcome."
    else:
        redirect_text="No redirect was recorded."
    final=result.final_url or ""
    try:
        parsed=urlsplit(final)
        host=parsed.hostname or ""
        safe_final=final if successful and parsed.scheme in ("http","https") and host and not parsed.username and not parsed.password else ""
    except ValueError:
        host="";safe_final=""
    product_code=""
    if host=="amazon.com" or host.endswith(".amazon.com"):
        match=re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)",urlsplit(final).path,re.I)
        if match: product_code=match.group(1)
    source_line=""
    if include_source:
        source_line=next((line for line in result.link.source.content.splitlines() if result.link.url in line),"")
    try:
        original=urlsplit(result.link.url)
        safe_original=result.link.url if successful and original.scheme in ("http","https") and original.hostname and not original.username and not original.password else ""
    except ValueError: safe_original=""
    return {
        "source_line":source_line,"safe_original_url":safe_original,
        "manual_label":{
            "unreviewed":"Not manually checked",
            "wrong_destination":"Wrong destination reported",
            "needs_owner":"Owner decision needed",
            "destination_verified":"Destination/product checked manually",
            "discount_unverified":"Discount not checked",
            "discount_verified":"Discount code checked manually",
            "replacement_proposed":"Replacement proposed — not applied",
        }.get(getattr(result,"manual_status","unreviewed"),"Manual review required"),
        "headline":headline,"assessment":assessment,"action":action,"tone":tone,
        "redirect_text":redirect_text,"redirect_count":len(redirects),
        "final_status":f"HTTP {status}" if status is not None else "No final HTTP response",
        "final_status_meaning":STATUS_MEANINGS.get(status,"Other response; see recorded reason"),
        "original_parameters":affiliate_query(result.link.url),
        "final_parameters":affiliate_query(final),
        "product_code":product_code,"final_host":host,"safe_final_url":safe_final,
        "steps":[dict(hop,number=index+1,meaning=STATUS_MEANINGS.get(hop.get("status"),"Recorded server response")) for index,hop in enumerate(chain)],
    }


def category_label(category):
    return {
        'destination_review':'HTTP response succeeded — manual destination check needed',
        'broken':'Missing/gone response — review replacement',
        'access_blocked':'Access denied or bot protection — inconclusive',
        'rate_limited':'Rate limited — retry later',
        'timeout':'Timed out — inconclusive',
        'server_error':'Server error — may be temporary',
        'network_error':'Network error — inconclusive',
        'unsafe_blocked':'Blocked by safety rules',
        'http_review':'Unexpected HTTP response — review needed',
    }.get(category,category)
