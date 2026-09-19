"""Read a restaurant's menu from its own website.

The most complete source when it works: a restaurant's site usually carries the whole menu, and
because it is the restaurant's own content rather than Google's, the result may be cached. But in
practice a menu turns up in four shapes, and one trap:

- **HTML text** on a /menu page — read the text, parse it as a menu.
- **A PDF** — read its text layer; if it's a scan, render the pages and read them as photos.
- **Images on the page** — plenty of small restaurants post photos of their printed menu.
- **An ordering platform** (Toast, Snackpass, Square…) — built in the browser with JavaScript, so
  a plain download is an empty shell. Reported honestly rather than guessed at.
- **The trap: a site that isn't theirs any more.** Expired restaurant domains get bought up. The
  site Google lists for Brothers Galbi in Los Angeles now serves an Indonesian gambling page. So a
  site must mention the restaurant before anything on it is trusted.

Fetching is careful because the addresses come from the internet: only public http(s) hosts,
redirects checked hop by hop, responses capped in size, robots.txt respected.
"""

from __future__ import annotations

import io
import ipaddress
import logging
import re
import socket
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from app.models.menu import ParsedMenu
from app.models.menu_sources import SourceReport, SourceResult, SourcedMenu
from app.services.menu_sources.quality import is_legible, item_count

logger = logging.getLogger(__name__)

BOT_NAME = "MenuistBot"
USER_AGENT = f"Mozilla/5.0 (compatible; {BOT_NAME}/0.1; +https://github.com/XuRunhui/menu-ai-app)"
TIMEOUT = 12
MAX_BYTES = 8_000_000
MAX_REDIRECTS = 5
MAX_MENU_PAGES = 3        # menu links followed from each page
MAX_FETCHES = 8           # pages downloaded in total, homepage included
MAX_DOCUMENTS = 5         # menu pages / PDFs parsed (lunch, dinner, drinks…)
MAX_MENU_IMAGES = 3       # menu photos read from one page
MAX_PDF_PAGES = 6
MIN_PRICES = 4            # a homepage with this many prices may be the menu itself
# A page reached through a "menu" link is parsed when it has real text, prices or not: Xi'an
# Famous Foods lists 40 dishes with no prices at all. Navigation and footers alone rarely pass this.
MIN_MENU_TEXT = 2500
MIN_VISIBLE_TEXT = 200    # less than this and the page needs a browser to show anything
MIN_MENU_IMAGE_WIDTH = 600
# Long menus are read in pieces, side by side: Katz's runs to 33,000 characters, and one reply
# that size is slow and was being cut off mid-JSON.
CHUNK_CHARS = 9000
MAX_CHUNKS = 6

# Link text or addresses that point at a menu, in the languages menus in this app come in.
_MENU_WORD = re.compile(r"menu|menú|carta|speisekarte|메뉴|菜单|菜單|メニュー|お品書き", re.I)
_PRICE = re.compile(r"[$€£¥₩]\s?\d{1,5}(?:[.,]\d{1,2})?|\b\d{1,4}[.,]\d{2}\b|\d{1,6}\s?(?:원|円|元)")
# Ordering platforms that assemble the menu in the browser; a plain download can't see it.
_PLATFORMS = {
    "toasttab.com": "Toast", "snackpass.co": "Snackpass", "square.site": "Square",
    "squareup.com": "Square", "chownow.com": "ChowNow", "doordash.com": "DoorDash",
    "grubhub.com": "Grubhub", "ubereats.com": "Uber Eats", "clover.com": "Clover",
    "popmenu.com": "Popmenu", "menufy.com": "Menufy", "olo.com": "Olo", "seamless.com": "Seamless",
    "order.online": "an online ordering site", "bentobox.com": "BentoBox",
}
# Words in a restaurant's name that say nothing about which restaurant it is.
_GENERIC_NAME_WORDS = {
    "the", "and", "of", "restaurant", "restaurants", "cafe", "café", "kitchen", "bar", "grill",
    "house", "eatery", "bistro", "dining", "co", "inc", "llc", "express", "place", "shop",
    "korean", "chinese", "japanese", "thai", "vietnamese", "mexican", "italian", "indian",
    "bbq", "barbecue", "sushi", "noodle", "noodles", "food", "foods", "tavern", "diner",
}
_BLOCK_TAGS = {"p", "div", "li", "tr", "td", "th", "br", "h1", "h2", "h3", "h4", "h5", "h6",
               "section", "article", "dd", "dt", "header", "footer", "table"}
_HIDDEN_TAGS = {"script", "style", "noscript", "template", "svg"}


# pdfium (Chromium's PDF engine, behind pypdfium2) is not thread-safe: two threads inside it at once
# crash the whole process — not the request, the server. Reproduced by reading Jerusalem Garden's
# menu PDF from six threads, which aborts the interpreter within a few rounds. Menu pages are read
# in parallel, so every use of pdfium goes through this lock.
_PDFIUM_LOCK = threading.Lock()


class UnsafeAddress(Exception):
    """The address points somewhere this server must not fetch (a private network, say)."""


# ─── Fetching ────────────────────────────────────────────────────────────────


@dataclass
class Fetched:
    url: str              # after redirects
    status: int
    content_type: str
    content: bytes

    @property
    def is_pdf(self) -> bool:
        return "pdf" in self.content_type or urlparse(self.url).path.lower().endswith(".pdf")

    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _check_public(url: str) -> None:
    """Refuse anything but a public http(s) host.

    Addresses come from the internet: a hostile page could link to this server's own network or
    the cloud metadata service. Every hop of every redirect goes through this.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeAddress(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, port,
                                                               proto=socket.IPPROTO_TCP)}
    except socket.gaierror as exc:
        raise requests.ConnectionError(f"can't resolve {parsed.hostname}") from exc
    for address in addresses:
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise UnsafeAddress(url)


def fetch(url: str, max_bytes: int = MAX_BYTES) -> Fetched:
    """GET a public URL, following redirects by hand so each hop is checked."""
    for _ in range(MAX_REDIRECTS + 1):
        _check_public(url)
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
                                allow_redirects=False, stream=True)
        if response.is_redirect and response.headers.get("location"):
            url = urljoin(url, response.headers["location"])
            response.close()
            continue

        chunks, total = [], 0
        for chunk in response.iter_content(64 * 1024):
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                break
        response.close()
        return Fetched(url=url, status=response.status_code,
                       content_type=response.headers.get("content-type", "").lower(),
                       content=b"".join(chunks)[:max_bytes])
    raise requests.TooManyRedirects(url)


def robots_allow(url: str) -> bool:
    """Whether the site's robots.txt lets us read this page. Unreadable robots.txt allows it."""
    parsed = urlparse(url)
    try:
        robots = fetch(f"{parsed.scheme}://{parsed.netloc}/robots.txt", max_bytes=500_000)
    except Exception:
        return True
    body = robots.text()
    # Some servers answer every path with their homepage; that isn't a robots file.
    if robots.status >= 400 or "<html" in body[:1000].lower():
        return True
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    return parser.can_fetch(BOT_NAME, url)


# ─── Reading a page ──────────────────────────────────────────────────────────


class _PageParser(HTMLParser):
    """Visible text, title, links and images from an HTML page, with no third-party parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: list[str] = []
        self.meta: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.images: list[tuple[str, str]] = []
        self._hidden = 0
        self._in_title = False
        self._link: Optional[list] = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in _HIDDEN_TAGS:
            self._hidden += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = attributes.get("name") or attributes.get("property") or ""
            if key in ("description", "og:site_name", "og:title", "og:description"):
                self.meta.append(attributes.get("content") or "")
        elif tag == "a" and attributes.get("href"):
            self._link = [attributes["href"], []]
        elif tag == "img":
            source = attributes.get("src") or attributes.get("data-src") or ""
            self.images.append((source, attributes.get("alt") or ""))
            if self._link is not None and attributes.get("alt"):
                self._link[1].append(attributes["alt"])
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _HIDDEN_TAGS and self._hidden:
            self._hidden -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._link is not None:
            self.links.append((self._link[0], " ".join(self._link[1]).strip()))
            self._link = None
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)
        elif not self._hidden:
            self.parts.append(data)
            if self._link is not None and data.strip():
                self._link[1].append(data.strip())


@dataclass
class Page:
    url: str
    text: str                     # visible text, one block per line
    identity_text: str            # title + meta + visible text, for checking whose site it is
    links: list[tuple[str, str]] = field(default_factory=list)
    images: list[tuple[str, str]] = field(default_factory=list)


def read_html(fetched: Fetched) -> Page:
    parser = _PageParser()
    try:
        parser.feed(fetched.text())
    except Exception:  # malformed HTML: keep whatever was parsed
        logger.debug("website: HTML parse stopped early on %s", fetched.url)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in "".join(parser.parts).split("\n")]
    text = "\n".join(line for line in lines if line)
    identity = " ".join([" ".join(parser.title), " ".join(parser.meta), text])
    return Page(url=fetched.url, text=text, identity_text=identity,
                links=parser.links, images=parser.images)


def price_count(text: str) -> int:
    return len(_PRICE.findall(text))


def pdf_text_and_images(content: bytes) -> tuple[str, list[bytes]]:
    """A PDF's text layer, and page images when it has none (a scanned menu)."""
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(content)
        try:
            pages = [pdf[index] for index in range(min(len(pdf), MAX_PDF_PAGES))]
            text = "\n".join(page.get_textpage().get_text_range() for page in pages)
            if len(text.strip()) >= MIN_VISIBLE_TEXT:
                return text, []
            images = []
            for page in pages:
                buffer = io.BytesIO()
                page.render(scale=2).to_pil().convert("RGB").save(buffer, format="JPEG", quality=85)
                images.append(buffer.getvalue())
            return "", images
        finally:
            pdf.close()


# ─── Whose site is this? ─────────────────────────────────────────────────────


def _identity_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"['’`]", "", text)                  # "Xi'an" -> "xian", "Joe's" -> "joes"
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


def name_tokens(name: str) -> list[str]:
    """The words that identify a restaurant: 'Brothers Galbi' -> ['brothers', 'galbi']."""
    # Google appends branch names: "Xi'an Famous Foods 西安名吃 | Chinatown", "Kanbu - Downtown".
    name = re.split(r"\s[|\-–—]\s|\s\(", name)[0]
    tokens = _identity_normalize(name).split()
    return [token for token in dict.fromkeys(tokens)
            if token not in _GENERIC_NAME_WORDS
            and (len(token) >= 3 or re.search(r"[^\x00-\x7f]", token))]


def belongs_to(restaurant_name: str, page: Page) -> Optional[bool]:
    """Whether this page is plausibly the restaurant's own. None when there's no way to tell."""
    tokens = name_tokens(restaurant_name)
    if not tokens or len(page.text) < MIN_VISIBLE_TEXT:
        return None
    haystack = _identity_normalize(page.identity_text)
    words, squashed = set(haystack.split()), haystack.replace(" ", "")
    found = sum(1 for token in tokens if token in words or token in squashed)
    return found / len(tokens) >= 0.6


# ─── Finding the menu ────────────────────────────────────────────────────────


def _site(host: str) -> str:
    """Rough registrable domain: 'www.xianfoods.com' -> 'xianfoods.com'."""
    parts = (host or "").lower().split(".")
    return ".".join(parts[-2:])


def _platform(url: str) -> Optional[str]:
    host = (urlparse(url).hostname or "").lower()
    return next((name for domain, name in _PLATFORMS.items() if host.endswith(domain)), None)


def menu_links(page: Page) -> tuple[list[str], list[str]]:
    """(menu pages worth reading, most likely first) and (ordering-platform links)."""
    home_site = _site(urlparse(page.url).hostname or "")
    scores: dict[str, int] = {}
    platforms: list[str] = []
    for href, label in page.links:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(page.url, href).split("#")[0]
        if not url.startswith("http") or url.rstrip("/") == page.url.rstrip("/"):
            continue
        is_menu = bool(_MENU_WORD.search(f"{href} {label}"))
        is_pdf = urlparse(url).path.lower().endswith(".pdf")
        if not (is_menu or is_pdf):
            continue
        if _platform(url):
            platforms.append(url)
            continue
        same_site = _site(urlparse(url).hostname or "") == home_site
        if not same_site and not is_pdf:
            continue  # social media and directories aren't the menu, and are often stale
        scores[url] = max(scores.get(url, 0), 3 * is_menu + 2 * is_pdf + 2 * same_site)
    ranked = sorted(scores, key=lambda url: -scores[url])
    return ranked, list(dict.fromkeys(platforms))


def menu_images(page: Page) -> list[str]:
    """Images on a page that look like photos of the menu."""
    urls = []
    for source, alt in page.images:
        if not source or source.startswith("data:"):
            continue
        # "menu.svg" is the hamburger icon in the navigation bar, not a menu.
        if urlparse(source).path.lower().endswith(".svg"):
            continue
        if _MENU_WORD.search(f"{source} {alt}"):
            urls.append(urljoin(page.url, source))
    return list(dict.fromkeys(urls))[:MAX_MENU_IMAGES]


# ─── Parsing ─────────────────────────────────────────────────────────────────


def as_jpeg(content: bytes, max_px: int = 2000) -> Optional[bytes]:
    """Re-encode any image Pillow can open as a JPEG the vision model accepts.

    Restaurant sites serve AVIF, WebP, PNG and SVG. DeepSeek rejects some of these outright, and a
    wrong label is enough to fail the call, so everything is normalised. Returns None for images
    too small to hold a readable menu, and for anything that isn't a raster image (SVG icons).
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            if image.width < MIN_MENU_IMAGE_WIDTH:
                return None
            image = image.convert("RGB")
            image.thumbnail((max_px, max_px))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88)
            return buffer.getvalue()
    except Exception:
        return None


def _combine_pages(menus: list[Optional[ParsedMenu]]) -> Optional[ParsedMenu]:
    from app.services.menu_sources.merge import combine

    usable = [menu for menu in menus if menu and menu.menu]
    if not usable:
        return None
    if len(usable) == 1:
        return usable[0]
    return combine([SourcedMenu(kind="website", menu=menu) for menu in usable]).menu


def _chunks(text: str) -> list[str]:
    """Split on line breaks into pieces of at most CHUNK_CHARS, keeping dishes whole."""
    pieces, current = [], ""
    for line in text.splitlines():
        if current and len(current) + len(line) + 1 > CHUNK_CHARS:
            pieces.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        pieces.append(current)
    return pieces[:MAX_CHUNKS]


def _parse_text(text: str, api_key: str, target_language: Optional[str]) -> Optional[ParsedMenu]:
    from app.services.vision_parser import parse_menu_text

    def parse(piece: str) -> Optional[ParsedMenu]:
        try:
            return parse_menu_text(piece, api_key, target_language)
        except Exception as exc:
            logger.info("website: couldn't parse part of a menu: %s", exc)
            return None

    pieces = _chunks(text)
    if len(pieces) == 1:
        return parse(pieces[0])
    with ThreadPoolExecutor(max_workers=len(pieces)) as pool:
        return _combine_pages(list(pool.map(parse, pieces)))


def _parse_images(images: list[bytes], api_key: str, target_language: Optional[str]) -> Optional[ParsedMenu]:
    from app.services.vision_parser import parse_menu_image

    readable = [jpeg for jpeg in (as_jpeg(image) for image in images) if jpeg]
    if not readable:
        return None

    def parse(image: bytes) -> Optional[ParsedMenu]:
        try:
            # Cached by the image's hash: reopening a restaurant with image or PDF menus
            # otherwise paid for every page to be read again.
            return parse_menu_image(image_source=image, api_key=api_key,
                                    target_language=target_language, cache=True)
        except Exception as exc:
            logger.info("website: couldn't read a menu image: %s", exc)
            return None

    with ThreadPoolExecutor(max_workers=len(readable)) as pool:
        return _combine_pages(list(pool.map(parse, readable)))


def _download_images(urls: list[str]) -> list[bytes]:
    def get(url: str) -> Optional[bytes]:
        try:
            fetched = fetch(url)
        except Exception:
            return None
        return fetched.content if fetched.status < 400 and fetched.content_type.startswith("image/") else None

    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=MAX_MENU_IMAGES) as pool:
        return [image for image in pool.map(get, urls) if image]


def read_document(fetched: Fetched, api_key: str, target_language: Optional[str],
                  from_menu_link: bool) -> Optional[ParsedMenu]:
    """Everything one page or PDF says about the menu: its text, and any photos of the menu on it."""
    if fetched.is_pdf:
        text, scans = pdf_text_and_images(fetched.content)
        return _parse_text(text, api_key, target_language) if text else \
            _parse_images(scans, api_key, target_language)

    page = read_html(fetched)
    found: list[Optional[ParsedMenu]] = []
    if price_count(page.text) >= MIN_PRICES or (from_menu_link and len(page.text) >= MIN_MENU_TEXT):
        found.append(_parse_text(page.text, api_key, target_language))
    found.append(_parse_images(_download_images(menu_images(page)), api_key, target_language))
    return _combine_pages(found)


@dataclass
class _Discovery:
    documents: list[tuple[Fetched, bool]] = field(default_factory=list)  # (page, via a menu link)
    platforms: list[str] = field(default_factory=list)


def discover(home: Fetched, home_page: Page) -> _Discovery:
    """Walk from the homepage to every menu it leads to, two links deep, without parsing yet.

    Two levels because menus hide one page further than you'd hope: Jerusalem Garden's /menu page
    says "download the PDF version", and Zingerman's /menus/ is an index of separate menus.
    """
    found = _Discovery()
    if price_count(home_page.text) >= MIN_PRICES:
        found.documents.append((home, False))

    links, platforms = menu_links(home_page)
    found.platforms += platforms
    queue = [(url, 1) for url in links[:MAX_MENU_PAGES]]
    visited, fetches = {home.url.rstrip("/")}, 1

    while queue and fetches < MAX_FETCHES and len(found.documents) < MAX_DOCUMENTS:
        url, depth = queue.pop(0)
        if url.rstrip("/") in visited:
            continue
        visited.add(url.rstrip("/"))
        try:
            fetched = fetch(url)
            fetches += 1
            if fetched.status >= 400 or not robots_allow(fetched.url):
                continue
        except Exception as exc:
            logger.info("website: couldn't open %s: %s", url, exc)
            continue
        visited.add(fetched.url.rstrip("/"))
        found.documents.append((fetched, True))

        if depth < 2 and not fetched.is_pdf:
            sub_links, sub_platforms = menu_links(read_html(fetched))
            found.platforms += sub_platforms
            queue += [(link, depth + 1) for link in sub_links[:MAX_MENU_PAGES]
                      if link.rstrip("/") not in visited]

    found.platforms = list(dict.fromkeys(found.platforms))
    return found


# ─── The source ──────────────────────────────────────────────────────────────


def _result(status: str, detail: str, menu: Optional[ParsedMenu] = None, url: Optional[str] = None,
            trusted: Optional[bool] = None) -> SourceResult:
    return SourceResult(
        report=SourceReport(kind="website", status=status, detail=detail, url=url,
                            item_count=item_count(menu) if menu else 0),
        menu=menu, website_trusted=trusted)


def read_website_menu(restaurant_name: str, website: Optional[str], api_key: str,
                      target_language: Optional[str] = "English") -> SourceResult:
    """Find and read the menu on the restaurant's own website."""
    if not website:
        return _result("none", "Google doesn't list a website for this restaurant.")
    host = urlparse(website).hostname or website

    try:
        home = fetch(website)
    except UnsafeAddress:
        return _result("unavailable", "The listed website address can't be opened safely.")
    except Exception as exc:
        logger.info("website: couldn't open %s: %s", website, exc)
        return _result("error", f"Couldn't open {host} ({type(exc).__name__}).")
    if home.status >= 400:
        return _result("unavailable", f"{host} returned an error ({home.status}).")
    if not robots_allow(home.url):
        return _result("unavailable", f"{host} asks automated tools not to read it.")

    if home.is_pdf:  # a few restaurants link straight to their menu PDF
        menu = _safe_read(home, api_key, target_language, True)
        if menu and is_legible(menu):
            return _result("found", f"Read {item_count(menu)} dishes from the menu PDF on {host}.",
                           menu, home.url, True)
        return _result("none", f"{host} links a PDF, but no menu could be read from it.")

    page = read_html(home)
    trusted = belongs_to(restaurant_name, page)
    if trusted is False:
        return _result("unavailable",
                       f"{host} no longer appears to be {restaurant_name}'s website — it shows "
                       "something unrelated now, so it was skipped.", trusted=False)

    discovery = discover(home, page)
    if discovery.documents:
        with ThreadPoolExecutor(max_workers=len(discovery.documents)) as pool:
            menus = list(pool.map(
                lambda document: _safe_read(document[0], api_key, target_language, document[1]),
                discovery.documents))
        menu = _combine_pages(menus)
        if menu and is_legible(menu):
            pages = [document.url for (document, _), m in zip(discovery.documents, menus)
                     if m and m.menu]
            where = urlparse(pages[0]).netloc + urlparse(pages[0]).path
            extra = f" and {len(pages) - 1} more page{'s' if len(pages) > 2 else ''}" if len(pages) > 1 else ""
            return _result("found", f"Read {item_count(menu)} dishes from {where}{extra}.",
                           menu, pages[0], trusted)

    if discovery.platforms:
        name = _platform(discovery.platforms[0])
        return _result("unavailable", f"The menu is on {name}, which only loads in a web browser, "
                       "so it can't be read here.", url=discovery.platforms[0], trusted=trusted)
    if trusted is None and len(page.text) < MIN_VISIBLE_TEXT:
        return _result("unavailable", f"{host} only shows its content in a web browser, "
                       "so it can't be read here.", trusted=None)
    if discovery.documents:
        return _result("none", f"Found a menu page on {host}, but no dishes could be read from it.",
                       trusted=trusted)
    return _result("none", f"{host} doesn't link to a menu.", trusted=trusted)


def _safe_read(fetched: Fetched, api_key: str, target_language: Optional[str],
               from_menu_link: bool) -> Optional[ParsedMenu]:
    try:
        return read_document(fetched, api_key, target_language, from_menu_link)
    except Exception as exc:
        logger.info("website: couldn't read %s: %s", fetched.url, exc)
        return None
