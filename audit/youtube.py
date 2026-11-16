"""Read-only public metadata via the official YouTube Data API."""
import json
import re
from urllib.parse import urlsplit, unquote, urlencode
from .network import fetch

class YouTubeError(ValueError):
    pass

def parse_channel(value):
    value = value.strip()
    if value.startswith("@"):
        value = "https://www.youtube.com/" + value
    p = urlsplit(value)
    try:
        valid = (p.scheme in ("https", "http") and p.hostname in
                 ("youtube.com", "www.youtube.com", "m.youtube.com")
                 and not p.username and not p.password and p.port in (None, 80, 443))
    except ValueError:
        valid = False
    if not valid:
        raise YouTubeError("Enter a youtube.com/@handle or youtube.com/channel/UC… URL.")
    path = unquote(p.path).rstrip("/")
    if re.fullmatch(r"/@[\w.\-·]{3,30}", path, re.UNICODE):
        return {"forHandle": path[1:]}, "https://www.youtube.com" + path
    if re.fullmatch(r"/channel/UC[A-Za-z0-9_-]{22}", path):
        return {"id": path.split("/")[-1]}, "https://www.youtube.com" + path
    if re.fullmatch(r"/user/[A-Za-z0-9_.-]{1,100}", path):
        return {"forUsername": path.split("/")[-1]}, "https://www.youtube.com" + path
    raise YouTubeError("Use a channel @handle, /channel/UC… or /user/ URL, not a video URL.")

def api(resource, key, **params):
    if resource not in ("channels", "playlistItems", "videos"):
        raise YouTubeError("Unsupported API operation")
    if not key or len(key) > 256 or any(c.isspace() for c in key):
        raise YouTubeError("Add a YouTube Data API key below, or configure YOUTUBE_API_KEY in this app's .env.")
    url = "https://www.googleapis.com/youtube/v3/" + resource + "?" + urlencode(params)
    try:
        status, final, chain, body = fetch(
            url, True, allowed_content_types=("application/json",),
            request_headers={"X-Goog-Api-Key": key}, follow_redirects=False)
    except Exception:
        # Never display transport exception text: credentials must not leak.
        raise YouTubeError("Could not reach the YouTube API. Check connectivity and retry.") from None
    if status != 200:
        if status in (400, 401):
            message = "YouTube rejected the key or request. Check the API key and channel URL."
        elif status in (403, 429):
            message = "YouTube denied this request. Check that YouTube Data API v3 is enabled, key restrictions allow this Mac, and quota remains."
        else:
            message = "YouTube API returned HTTP " + str(status) + ". Retry later."
        raise YouTubeError(message)
    try:
        data = json.loads(body)
        if not isinstance(data, dict): raise ValueError()
        return data
    except (ValueError, TypeError):
        raise YouTubeError("YouTube returned an invalid response.") from None

def load_channel(value, key, page_token=""):
    selector, canonical = parse_channel(value)
    data = api("channels", key, part="snippet,contentDetails", **selector)
    items = data.get("items", [])
    if len(items) != 1:
        raise YouTubeError("Channel not found. Check the handle or use its channel-ID URL.")
    channel = items[0]
    channel_id = channel.get("id", "")
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise YouTubeError("YouTube returned an invalid channel ID.")
    playlist = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not playlist:
        raise YouTubeError("No public uploads playlist is available.")
    params = dict(part="contentDetails", playlistId=playlist, maxResults=50)
    if page_token:
        if len(page_token) > 512: raise YouTubeError("Invalid page token")
        params["pageToken"] = page_token
    page = api("playlistItems", key, **params)
    ids = [item.get("contentDetails", {}).get("videoId", "") for item in page.get("items", [])]
    ids = list(dict.fromkeys(v for v in ids if re.fullmatch(r"[A-Za-z0-9_-]{11}", v)))[:50]
    by_id = {}
    if ids:
        details = api("videos", key, part="snippet,status", id=",".join(ids), maxResults=50)
        for item in details.get("items", []):
            snippet = item.get("snippet", {})
            if item.get("id") not in ids or snippet.get("channelId") != channel_id:
                continue
            if item.get("status", {}).get("privacyStatus") != "public":
                continue
            description = snippet.get("description", "")
            by_id[item["id"]] = {
                "id": item["id"], "title": snippet.get("title", "Untitled")[:200],
                "description": description[:100000], "published": snippet.get("publishedAt", ""),
                "url": "https://www.youtube.com/watch?v=" + item["id"],
            }
    return {"channel_id": channel_id, "channel_url": canonical,
            "channel_title": channel.get("snippet", {}).get("title", canonical)[:200],
            "videos": [by_id[v] for v in ids if v in by_id],
            "next_page": page.get("nextPageToken", "")[:512]}
