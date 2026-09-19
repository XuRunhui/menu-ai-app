"""Tests for reading a restaurant's menu from its own website.

The fake web below reproduces sites met for real: a domain taken over by a gambling page (Brothers
Galbi), a menu with no prices (Xi'an Famous Foods), a menu PDF one link past the menu page
(Jerusalem Garden), a hamburger icon called menu.svg, and an ordering platform.
"""

import io
import re
from types import SimpleNamespace

import pytest
from PIL import Image

from app.models.menu import MenuCategory, MenuItem, ParsedMenu
from app.services.menu_sources import website
from app.services.menu_sources.website import Fetched, UnsafeAddress

FILLER = "<p>" + ("Family owned since 1998, serving the neighbourhood every day. " * 12) + "</p>"


def _dishes(*names, price=True):
    return " ".join(f"<p>DISH:{name}{' $12.50' if price else ''}</p>" for name in names)


class FakeWeb:
    """Serves a dict of url -> (content type, body) and records every fetch."""

    def __init__(self, pages):
        self.pages = {url.rstrip("/"): page for url, page in pages.items()}
        self.fetched: list[str] = []

    def fetch(self, url, max_bytes=website.MAX_BYTES):
        self.fetched.append(url)
        page = self.pages.get(url.rstrip("/"))
        if page is None:
            return Fetched(url=url, status=404, content_type="text/html", content=b"")
        content_type, body = page
        return Fetched(url=url, status=200, content_type=content_type,
                       content=body if isinstance(body, bytes) else body.encode())


@pytest.fixture
def parsed(monkeypatch):
    """Stand-in parsers: 'DISH:<name>' markers in the text become dishes."""
    calls = []

    def parse_text(text, api_key, target_language=None, **kwargs):
        calls.append(("text", len(text)))
        names = re.findall(r"DISH:([^$<\n]+?)(?:\s\$|\n|$)", text)
        return ParsedMenu(detected_language="English", menu=[
            MenuCategory(category="Menu", items=[MenuItem(name=n.strip(), price=12.5) for n in names])])

    def parse_image(image_source, api_key, target_language=None, **kwargs):
        calls.append(("image", len(image_source)))
        return ParsedMenu(detected_language="English", menu=[MenuCategory(
            category="Photo", items=[MenuItem(name=f"Pictured Dish {i}") for i in range(5)])])

    monkeypatch.setattr("app.services.vision_parser.parse_menu_text", parse_text)
    monkeypatch.setattr("app.services.vision_parser.parse_menu_image", parse_image)
    monkeypatch.setattr(website, "robots_allow", lambda url: True)
    return calls


def _serve(monkeypatch, pages) -> FakeWeb:
    web = FakeWeb(pages)
    monkeypatch.setattr(website, "fetch", web.fetch)
    return web


def _read(name="Corner Tofu", site="https://cornertofu.com"):
    return website.read_website_menu(name, site, "key")


# ─── Finding the menu ────────────────────────────────────────────────────────


def test_a_menu_page_linked_from_the_homepage_is_read(monkeypatch, parsed):
    _serve(monkeypatch, {
        "https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}"
                                                '<a href="/menu">Our Menu</a>'),
        "https://cornertofu.com/menu": ("text/html", _dishes(*[f"Stew {i}" for i in range(6)])),
    })
    result = _read()
    assert result.report.status == "found" and result.report.item_count == 6
    assert result.report.url == "https://cornertofu.com/menu"
    assert result.website_trusted is True


def test_a_menu_without_prices_is_still_read(monkeypatch, parsed):
    # Xi'an Famous Foods lists its dishes with no prices; judging "is this a menu" by prices failed.
    text = _dishes(*[f"Noodle Dish {i}" for i in range(6)], price=False) + FILLER * 5
    _serve(monkeypatch, {
        "https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}"
                                                '<a href="/menu">Menu</a>'),
        "https://cornertofu.com/menu": ("text/html", text),
    })
    assert _read().report.status == "found"


def test_a_menu_pdf_one_link_past_the_menu_page_is_read(monkeypatch, parsed):
    # Jerusalem Garden: /menu says "download the PDF version".
    monkeypatch.setattr(website, "pdf_text_and_images",
                        lambda content: ("\n".join(f"DISH:Plate {i} $9.00" for i in range(8)), []))
    _serve(monkeypatch, {
        "https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}"
                                                '<a href="/menu">Menu</a>'),
        "https://cornertofu.com/menu": ("text/html", 'Download <a href="/files/menu.pdf">PDF Menu</a>'),
        "https://cornertofu.com/files/menu.pdf": ("application/pdf", b"%PDF-1.4 fake"),
    })
    result = _read()
    assert result.report.status == "found" and result.report.item_count == 8


def test_every_menu_page_is_combined_not_just_the_first(monkeypatch, parsed):
    _serve(monkeypatch, {
        "https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}"
                                                '<a href="/lunch-menu">Lunch Menu</a>'
                                                '<a href="/dinner-menu">Dinner Menu</a>'),
        "https://cornertofu.com/lunch-menu": ("text/html", _dishes("Bibimbap", "Mandu", "Japchae", "Tteokbokki")),
        "https://cornertofu.com/dinner-menu": ("text/html", _dishes("Galbi", "Bulgogi", "Samgyeopsal", "Jjim")),
    })
    result = _read()
    assert result.report.item_count == 8 and "1 more page" in result.report.detail


def test_photos_of_the_menu_on_the_page_are_read(monkeypatch, parsed):
    buffer = io.BytesIO()
    Image.new("RGB", (1200, 900)).save(buffer, format="WEBP")    # DeepSeek rejects some formats
    _serve(monkeypatch, {
        "https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}"
                                                '<a href="/menu">Menu</a>'),
        "https://cornertofu.com/menu": ("text/html", '<img src="/img/dinner-menu.webp" alt="menu">'),
        "https://cornertofu.com/img/dinner-menu.webp": ("image/webp", buffer.getvalue()),
    })
    assert _read().report.status == "found"
    assert ("image", pytest.approx(0, abs=10**7)) in [(kind, n) for kind, n in parsed]


def test_a_hamburger_icon_called_menu_is_not_a_menu(monkeypatch, parsed):
    page = website.read_html(Fetched("https://cornertofu.com/menu", 200, "text/html",
                                     b'<img src="/icons/menu.svg"><img src="/photos/menu-page1.jpg">'))
    assert website.menu_images(page) == ["https://cornertofu.com/photos/menu-page1.jpg"]


# ─── When there's nothing to read ────────────────────────────────────────────


def test_a_domain_taken_over_by_another_site_is_skipped(monkeypatch, parsed):
    # brothergalbi.com, listed on Google, now serves an Indonesian gambling page.
    gambling = ("<title>BigWin365: Destinasi Slot Gambling Terbaik</title>"
                + "<p>Slot online terpercaya, casino, poker, togel. </p>" * 30 + '<a href="/menu">Menu</a>')
    web = _serve(monkeypatch, {"https://brothergalbi.com": ("text/html", gambling)})
    result = website.read_website_menu("Brothers Galbi", "https://brothergalbi.com", "key")

    assert result.report.status == "unavailable" and result.website_trusted is False
    assert "no longer appears to be Brothers Galbi's website" in result.report.detail
    assert web.fetched == ["https://brothergalbi.com"]          # nothing further is touched
    assert parsed == []                                          # and nothing is paid for


def test_an_ordering_platform_is_reported_not_guessed_at(monkeypatch, parsed):
    _serve(monkeypatch, {"https://cornertofu.com": (
        "text/html", f"<title>Corner Tofu</title>{FILLER}"
                     '<a href="https://order.toasttab.com/online/corner-tofu">Order / Menu</a>')})
    result = _read()
    assert result.report.status == "unavailable" and "Toast" in result.report.detail
    assert parsed == []


def test_a_site_that_needs_a_browser_says_so(monkeypatch, parsed):
    _serve(monkeypatch, {"https://cornertofu.com": ("text/html", '<div id="root"></div>')})
    result = _read()
    assert result.report.status == "unavailable" and "web browser" in result.report.detail


def test_robots_txt_is_respected(monkeypatch, parsed):
    _serve(monkeypatch, {"https://cornertofu.com": ("text/html", "<title>Corner Tofu</title>")})
    monkeypatch.setattr(website, "robots_allow", lambda url: False)
    assert "asks automated tools not to read it" in _read().report.detail


def test_no_website_listed(parsed):
    assert website.read_website_menu("Corner Tofu", None, "key").report.status == "none"


def test_a_site_without_a_menu_link(monkeypatch, parsed):
    _serve(monkeypatch, {"https://cornertofu.com": ("text/html", f"<title>Corner Tofu</title>{FILLER}")})
    assert _read().report.detail == "cornertofu.com doesn't link to a menu."


# ─── Whose site is it ────────────────────────────────────────────────────────


def test_restaurant_names_are_reduced_to_what_identifies_them():
    assert website.name_tokens("Brothers Galbi") == ["brothers", "galbi"]
    assert website.name_tokens("Xi'an Famous Foods 西安名吃 | Chinatown") == ["xian", "famous", "西安名吃"]
    assert website.name_tokens("Tomukun Korean BBQ") == ["tomukun"]
    assert website.name_tokens("The Kitchen") == []          # nothing distinctive: can't tell


def test_a_page_mentioning_most_of_the_name_belongs_to_it():
    page = website.read_html(Fetched("https://xianfoods.com", 200, "text/html",
                                     f"<title>Xi’an Famous Foods</title>{FILLER}".encode()))
    assert website.belongs_to("Xi'an Famous Foods 西安名吃 | Chinatown", page) is True


# ─── Reading long menus ──────────────────────────────────────────────────────


def test_a_long_menu_is_read_in_pieces_and_combined(monkeypatch, parsed):
    lines = [f"DISH:Sandwich Number {i} $15.00" for i in range(900)]      # ~30k characters
    menu = website._parse_text("\n".join(lines), "key", "English")
    assert len([c for c in parsed if c[0] == "text"]) > 1
    assert sum(len(c.items) for c in menu.menu) == 900
    assert all(n <= website.CHUNK_CHARS + 100 for _, n in parsed)


# ─── Fetching safely ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost:8000/api", "http://169.254.169.254/computeMetadata/v1/",
    "http://10.0.0.5/", "http://[::1]/", "ftp://cornertofu.com/menu.pdf", "file:///etc/passwd",
])
def test_private_and_non_web_addresses_are_refused(url):
    with pytest.raises(UnsafeAddress):
        website._check_public(url)


def test_a_redirect_into_the_private_network_is_refused(monkeypatch):
    monkeypatch.setattr(website, "_check_public", lambda url: (_ for _ in ()).throw(UnsafeAddress(url))
                        if "169.254" in url else None)
    redirect = SimpleNamespace(is_redirect=True, headers={"location": "http://169.254.169.254/"},
                               close=lambda: None)
    monkeypatch.setattr(website.requests, "get", lambda *a, **kw: redirect)
    with pytest.raises(UnsafeAddress):
        website.fetch("https://cornertofu.com/menu")


def test_robots_rules_for_this_bot_are_honoured(monkeypatch):
    body = "User-agent: MenuistBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    monkeypatch.setattr(website, "fetch", lambda url, max_bytes=0: Fetched(url, 200, "text/plain", body.encode()))
    assert website.robots_allow("https://cornertofu.com/menu") is False


def test_a_homepage_served_as_robots_txt_is_ignored(monkeypatch):
    monkeypatch.setattr(website, "fetch", lambda url, max_bytes=0: Fetched(
        url, 200, "text/html", b"<!doctype html><html><title>BigWin365</title>"))
    assert website.robots_allow("https://brothergalbi.com/") is True


# ─── Images ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["PNG", "WEBP", "AVIF"])
def test_web_image_formats_become_jpegs(fmt):
    buffer = io.BytesIO()
    Image.new("RGB", (1200, 900), (200, 50, 50)).save(buffer, format=fmt)
    assert website.as_jpeg(buffer.getvalue()).startswith(b"\xff\xd8\xff")


def test_icons_and_vectors_are_not_menu_images():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64)).save(buffer, format="PNG")
    assert website.as_jpeg(buffer.getvalue()) is None
    assert website.as_jpeg(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') is None


def test_pdf_reading_never_runs_on_two_threads_at_once(monkeypatch):
    # pdfium isn't thread-safe: concurrent use aborted the whole server process (reproduced with
    # a real menu PDF). This checks the lock deterministically, without risking the crash itself.
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    import pypdfium2

    inside, peak, counter = [0], [0], threading.Lock()

    class FakePage:
        def get_textpage(self):
            return SimpleNamespace(get_text_range=lambda: "DISH:Hummus $5.50\n" * 20)

    class FakePdf:
        def __init__(self, content):
            with counter:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
            time.sleep(0.01)

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return FakePage()

        def close(self):
            with counter:
                inside[0] -= 1

    monkeypatch.setattr(pypdfium2, "PdfDocument", FakePdf)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: website.pdf_text_and_images(b"%PDF-1.4"), range(16)))
    assert peak[0] == 1


def test_menu_images_from_a_website_are_read_with_the_cache_on(monkeypatch):
    # A restaurant's menu images and PDF pages are the same on every visit; reading them again
    # paid for every page each time the restaurant was opened.
    from app.services import vision_parser

    seen = []

    def fake_parse_menu_image(**kwargs):
        seen.append(kwargs.get("cache"))
        return ParsedMenu(menu=[MenuCategory(category="Mains", items=[MenuItem(name="Galbi")])])

    monkeypatch.setattr(vision_parser, "parse_menu_image", fake_parse_menu_image)
    buffer = io.BytesIO()
    Image.new("RGB", (website.MIN_MENU_IMAGE_WIDTH + 200, 900), "white").save(buffer, format="PNG")
    assert website._parse_images([buffer.getvalue()], "key", "English") is not None
    assert seen == [True]
