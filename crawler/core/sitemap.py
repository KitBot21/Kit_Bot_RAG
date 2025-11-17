from __future__ import annotations
from urllib.parse import urlparse
from .fetch import fetch_text
import xml.etree.ElementTree as ET

SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

def _canon_loc(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    bad_prefix = "http://www.kumoh.ac.krhttps://"
    if u.startswith(bad_prefix):
        u = u[len("http://www.kumoh.ac.kr"):]
    u = u.replace("http://www.kumoh.ac.kr", "https://www.kumoh.ac.kr")
    return u

def parse_sitemap(url: str, headers: dict, timeout: int, allow_sections: list[str] | None, out_urls: dict[str, str | None]):
    xml = fetch_text(url, headers=headers, timeout=timeout)
    if not xml:
        return
    try:
        root = ET.fromstring(xml)
    except Exception:
        return

    tag = root.tag.split("}")[-1]
    if tag == "sitemapindex":
        for loc_el in root.findall(".//sm:loc", SM_NS):
            if not (loc_el.text and loc_el.text.strip()):
                continue
            loc = _canon_loc(loc_el.text)
            if allow_sections:
                try:
                    sec = urlparse(loc).path.strip("/").split("/")[0]
                except Exception:
                    sec = ""
                if sec not in set(allow_sections):
                    continue
            parse_sitemap(loc, headers, timeout, allow_sections, out_urls)
    elif tag == "urlset":
        for url_el in root.findall(".//sm:url", SM_NS):
            loc_el = url_el.find("sm:loc", SM_NS)
            if loc_el is None or not (loc_el.text and loc_el.text.strip()):
                continue
            loc = _canon_loc(loc_el.text)
            lastmod_el = url_el.find("sm:lastmod", SM_NS)
            lastmod = (lastmod_el.text.strip() if (lastmod_el is not None and lastmod_el.text) else None)
            out_urls[loc] = lastmod

def seed_from_sitemaps(index_url: str, headers: dict, timeout: int, allow_sections: list[str] | None) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    parse_sitemap(index_url, headers, timeout, allow_sections, out)
    return out