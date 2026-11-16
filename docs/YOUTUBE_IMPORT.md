# Public YouTube channel import

This standalone local application accepts @handle, /channel/UC… and legacy /user/ channel
URLs through the project's **Import from YouTube channel** screen. Share parameters such
as `si` are discarded. The supplied channel normalizes to:
https://www.youtube.com/@madmallardsadventures

## Setup and use
1. Sign into the app and open the Mad Mallards Adventures project.
2. Choose Import from YouTube channel. The supplied channel URL is prefilled locally.
3. Supply a YouTube Data API v3 key. The key must belong to an API project with that API
   enabled. No key is borrowed from any other application or repository. This app does not
   create Google Cloud projects, enable billing, purchase anything or raise quotas.
4. Click Load channel videos, select up to the remaining source limit (maximum 20), confirm
   ownership/permission and retention terms, then Import selected descriptions.
5. Successful loads open the dedicated **Loaded videos** page. Bookmark its URL or use
   **Your results → View loaded videos** on the project. Each saved page has a stable URL. Returning
   to the same project restores the latest unexpired preview for your account, without
   another API call. Loading indicators, explicit empty/error states, selection counts and
   select-first/clear controls make the current step visible.
6. Importing descriptions opens the dedicated **Imported descriptions & links** page.
   Reopen it from **Your results → View imported descriptions**. Start the initial scan
   there, then reopen the report from **Your results → View latest scan report**. The existing scanner checks up to 100 unique
   outbound URLs while keeping every video's title, watch URL and original description.
7. Browse older uploads 50 per page. Import a selection before moving to the next page.
   Repeated imports skip existing video IDs. Only public videos from the resolved channel
   are eligible. Private/deleted/unavailable videos are omitted. No page scraping fallback.

A key supplied in the form is used in memory for that load request, not stored in sessions,
previews or reports. Optional operator configuration: set YOUTUBE_API_KEY in this app's
ignored .env and run `docker compose up -d --no-deps web`. Never commit the key. Restrict
it to YouTube Data API v3 and appropriate server access. Browser HTTP-referrer restrictions
are not suitable for requests sent by this local server.

The screen does not OAuth-connect a Google account. Public metadata works with an API key;
this is not proof of channel ownership. User permission is explicitly attested before import.
Account/private-video access or write operations would require a separately scoped feature.

## API and safety
Official GET endpoints only: channels.list (forHandle/id/forUsername), playlistItems.list
(the channel's uploads playlist), videos.list (full descriptions and channel validation).
At most three list calls load one page. Do not equate this to a guaranteed quota allocation;
Google's project quota and errors apply. No paid API, write method, media download, account
scraping, affiliate-ID change or publication is performed.

Requests use audit.network's DNS/IP validation and TLS-hostname pinning, a fixed Google API
host, an API-key header (not a URL parameter), no redirects and a 1 MB response cap. API and
transport errors are sanitized. No new runtime dependency is needed. Saved video-list IDs
are scoped to both the logged-in user and project and expire 29 days after retrieval. Imports are
transactional, respect frozen sources/project limits and preserve encoded affiliate values.

## Retention and deletion
Imported YouTube source metadata expires no later than its originating saved list, with a maximum 29-day lifetime (under Google's 30-day refresh/delete
window). On subsequent app requests, expired previews and expired API sources are deleted;
source deletion also removes their links and associated result rows. Owner-pasted/uploaded
sources are unaffected. This is request-triggered cleanup, not a new scheduled task. An idle
or stopped app does not run cleanup until its next request; expired content is purged before
serving app pages. Reimport into a fresh project to get current descriptions.

The import screen explains this before consent. A confirmed **Delete local YouTube data**
action removes imported sources/results, previews and saved channel URL for that project.
This only deletes local data; it does not affect YouTube. Independently copied backups and
exports are the operator's responsibility: remove/refresh API-derived metadata within the
applicable retention period, including old backup copies. No automatic backup/export cleanup
or assertion of complete hosted-service compliance is provided.

YouTube Terms: https://www.youtube.com/t/terms
Google Privacy Policy: https://policies.google.com/privacy
Developer policies: https://developers.google.com/youtube/terms/developer-policies
API key setup: https://developers.google.com/youtube/data/getting-started
Channels lookup: https://developers.google.com/youtube/data/reference/rest/v3/channels/list
Uploads: https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list
Video descriptions: https://developers.google.com/youtube/data/reference/rest/v3/videos/list
API-key headers: https://docs.cloud.google.com/apis/docs/system-parameters

## Verification boundaries
Unit/integration fixtures cover official API requests, user/project isolation, imports,
provenance, deduplication, encoded parameters, consent, expiry/deletion, key redaction and
CSRF. Real extraction is also checked in the Docker image. No app-specific API key was
available at implementation time; live Mad Mallards Adventures catalogue retrieval and
actual channel audit must not be claimed until an authorized key is supplied and exercised.

Loaded video lists remain available when navigating away; they no longer expire after
30 minutes. Older saved pages are not removed merely because another page was loaded.
A one-time migration extends existing unexpired lists to 29 days from their original
retrieval time, without refetching or claiming their metadata was refreshed. Sign-in
returns to a bookmarked results page using a same-host-validated return URL.
