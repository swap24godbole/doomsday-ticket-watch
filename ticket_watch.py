"""Free, single-purpose Avengers: Doomsday ICE 3D booking-date monitor.

Uses only the Python standard library. Checks a public theatre-specific listing,
not seat inventory. Never purchases tickets or bypasses site access controls.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, date
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

LISTING_URL = (
    "https://ticketradar.in/f/avengers-doomsday/"
    "national-capital-region-ncr/theatre/paeg-gurugram-pepsi-pvr-ambience"
)
BOOK_URL = "https://in.bookmyshow.com/movies/national-capital-region-ncr/avengers-doomsday/ET00439706"
TARGET_DATE = date(2026, 12, 18)
CUTOFF_DATE = date(2026, 12, 19)
TIME_ZONE = ZoneInfo("Asia/Kolkata")
USER_AGENT = "PersonalTicketAvailabilityMonitor/1.0 (manual booking only)"
REQUEST_TIMEOUT = 20


class ListingError(Exception):
    """Failed to fetch or confidently interpret the public listing."""


class ListItems(HTMLParser):
    """Extract visible text from list items without HTML dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._level = 0
        self._parts: list[str] = []
        self.items: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            if self._level == 0:
                self._parts = []
            self._level += 1

    def handle_data(self, data: str) -> None:
        if self._level:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._level:
            self._level -= 1
            if not self._level:
                self.items.append(" ".join(" ".join(self._parts).split()))
                self._parts = []


def parse_listing(html: str) -> tuple[list[str], int]:
    """Return 18-Dec ICE-3D session lines and number of session lines inspected.

    Fails closed on unexpected page formats rather than returning false 'no tickets'.
    """
    if "Avengers: Doomsday" not in html or "PVR Ambience" not in html:
        raise ListingError("Expected movie/cinema markers missing; page may be blocked")
    if not re.search(r"\bshows?\s+listed\s+on\s+BookMyShow\b", html, re.I):
        # HTML could contain markup between words, so also check plain text below.
        stripped = re.sub(r"<[^>]+>", " ", html)
        if not re.search(r"\bshows?\s+listed\s+on\s+BookMyShow\b", stripped, re.I):
            raise ListingError("Show-list marker missing; unexpected site layout")

    parser = ListItems()
    parser.feed(html)
    # Exact date and venue are already scoped by URL. Avoid other page lists.
    sessions = [
        line for line in parser.items
        if re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+Dec\b", line, re.I)
    ]
    if not sessions and not re.search(r"\b0\s+shows\s+listed\s+on\s+BookMyShow\b", html, re.I):
        raise ListingError("No machine-readable session rows found; parser may need updating")

    hits = [
        line for line in sessions
        if re.search(r"\bFri\s+18\s+Dec\b", line, re.I)
        and re.search(r"\bICE\b", line, re.I)
        and re.search(r"\b3D\b", line, re.I)
    ]
    return hits, len(sessions)


def fetch_listing() -> str:
    req = Request(
        LISTING_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type:
                raise ListingError(f"Unexpected content type: {content_type[:80]}")
            return response.read(2_000_000).decode("utf-8", "replace")
    except HTTPError as exc:
        raise ListingError(f"HTTP {exc.code}; listing may block automated access") from None
    except (URLError, TimeoutError, OSError) as exc:
        # Don't include unknown URLs or secrets from exception objects in logs.
        raise ListingError(f"Network error ({type(exc).__name__})") from None


def telegram_message(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    from urllib.parse import urlencode
    body = urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    req = Request(
        f"https://api.telegram.org/bot{quote(token, safe=':')}/sendMessage",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read())
            if not data.get("ok"):
                raise RuntimeError("Telegram returned ok=false")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Exception strings can include the secret-bearing Telegram URL: suppress them.
        raise RuntimeError(f"Telegram send failed ({type(exc).__name__})") from None


def disable_own_workflow() -> None:
    """Stop future checks automatically, using Actions-scoped built-in GH token."""
    token = os.getenv("GH_TOKEN", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not (token and re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo)):
        raise RuntimeError("Missing GH_TOKEN or GITHUB_REPOSITORY (GitHub Actions only)")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/ticket-monitor.yml/disable"
    req = Request(
        url, method="PUT", data=b"",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 204:
                raise RuntimeError(f"GitHub returned HTTP {response.status} disabling workflow")
    except HTTPError as exc:
        raise RuntimeError(f"Could not disable workflow (GitHub HTTP {exc.code})") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not disable workflow ({type(exc).__name__})") from None


def run(automated: bool) -> int:
    now = datetime.now(TIME_ZONE)
    if now.date() >= CUTOFF_DATE:
        print("Target date has passed. Stopping the monitoring workflow.")
        if automated:
            disable_own_workflow()
        return 0
    print(f"Checking {TARGET_DATE.isoformat()} ICE 3D — {now:%Y-%m-%d %H:%M:%S %Z}")
    try:
        matches, inspected = parse_listing(fetch_listing())
    except ListingError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        if automated:
            # Fail closed: an error alert, then stop rather than miss tickets silently
            # or repeatedly pester a third-party site that's blocking us.
            telegram_message(
                "⚠️ Avengers ticket checker needs attention.\n"
                f"Could not read the booking listing: {exc}.\n"
                "Monitoring has stopped; please check the link manually:\n"
                + LISTING_URL
            )
            disable_own_workflow()
        return 1

    print(f"Inspected {inspected} session(s); target ICE 3D matches: {len(matches)}")
    if not matches:
        print("No December 18 ICE 3D listing detected yet (not a seat-availability check).")
        return 0

    for line in matches:
        print("MATCH:", line)
    if automated:
        telegram_message(
            "🎟️ DOOMSDAY — DEC 18 ICE 3D LISTED!\n"
            "PVR Ambience Mall, Gurugram\n\n"
            + "\n".join(matches[:10])
            + "\n\nBook on BookMyShow (select 18 Dec + ICE 3D):\n"
            + BOOK_URL
            + "\nListing source: " + LISTING_URL
            + "\n\nThis is a showtime listing, not guaranteed seat availability."
        )
        disable_own_workflow()
        print("Telegram alert sent; monitoring workflow disabled.")
    return 0


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"check", "run", "test-alert"}:
        print("Usage: ticket-watch [check|run|test-alert]", file=sys.stderr)
        raise SystemExit(2)
    command = sys.argv[1]
    if command == "test-alert":
        telegram_message("✅ Your free Avengers ticket monitor can reach Telegram.")
        print("Telegram test message sent.")
        return
    raise SystemExit(run(automated=(command == "run")))


if __name__ == "__main__":
    main()
