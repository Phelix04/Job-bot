"""
Job sources that work by reading public search-result pages (no API
available for these sites). These are the most likely part of the bot
to need a small fix later if a site redesigns its pages - see the
"If a scraper stops finding jobs" section in README.md.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 20


def _get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def _clean_text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _matches_keywords(title, keywords):
    """Safety-net filter: even though each source is queried with a
    keyword in the search URL, a site's own search can return loosely
    related jobs. This makes sure only jobs whose title actually
    contains one of our keywords get sent.
    """
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


def fetch_jobberman(keywords, max_per_keyword=15):
    """Jobberman search: https://www.jobberman.com/jobs?q=<keyword>
    Job listings link to /listings/<slug>, which is a stable URL
    pattern even if Jobberman changes its page design around it.
    """
    jobs = []
    for kw in keywords:
        url = f"https://www.jobberman.com/jobs?q={quote_plus(kw)}"
        try:
            soup = _get_soup(url)
        except Exception as e:
            print(f"[jobberman] fetch failed for '{kw}': {e}")
            continue

        links = soup.find_all("a", href=re.compile(r"^/listings/[\w-]+"))
        count = 0
        for a in links:
            if count >= max_per_keyword:
                break
            title = a.get("title") or _clean_text(a)
            if not title:
                continue
            href = a["href"]
            full_url = f"https://www.jobberman.com{href}" if href.startswith("/") else href

            # best-effort company/location: look at the nearby card text
            company = ""
            card = a.find_parent(["div", "article", "li"])
            if card:
                card_text = _clean_text(card)
                # company/location usually appears right after the title
                remainder = card_text.replace(title, "", 1).strip()
                company = remainder[:80]

            if not _matches_keywords(title, keywords):
                continue

            jobs.append({
                "source": "Jobberman",
                "title": title,
                "company": company,
                "location": "Nigeria",
                "url": full_url,
                "id": f"jobberman:{href}",
            })
            count += 1
        time.sleep(1)  # be polite between requests
    return jobs


def fetch_myjobmag(keywords, max_per_keyword=15):
    """MyJobMag search: https://www.myjobmag.com/search/jobs?q=<keyword>
    No public API, and the exact page structure wasn't verified while
    building this bot, so this uses a generic link-pattern scraper.
    If this stops returning results, see README.md for how to fix it.
    """
    jobs = []
    for kw in keywords:
        url = f"https://www.myjobmag.com/search/jobs?q={quote_plus(kw)}"
        try:
            soup = _get_soup(url)
        except Exception as e:
            print(f"[myjobmag] fetch failed for '{kw}': {e}")
            continue

        links = soup.find_all("a", href=re.compile(r"/job/[\w-]+"))
        count = 0
        seen_hrefs = set()
        for a in links:
            if count >= max_per_keyword:
                break
            href = a.get("href", "")
            if not href or href in seen_hrefs:
                continue
            title = _clean_text(a)
            if not title or len(title) < 6:
                continue  # skip nav/footer links with tiny text
            if not _matches_keywords(title, keywords):
                continue
            seen_hrefs.add(href)
            full_url = href if href.startswith("http") else f"https://www.myjobmag.com{href}"

            jobs.append({
                "source": "MyJobMag",
                "title": title,
                "company": "",
                "location": "Nigeria",
                "url": full_url,
                "id": f"myjobmag:{href}",
            })
            count += 1
        time.sleep(1)
    return jobs


def fetch_naijaremotejobs(keywords, max_per_keyword=15):
    """NaijaRemoteJobs: https://naijaremotejobs.com/?s=<keyword>
    (WordPress-style search). No public API; generic link-pattern
    scraper, same caveat as MyJobMag above.
    """
    jobs = []
    for kw in keywords:
        url = f"https://naijaremotejobs.com/?s={quote_plus(kw)}"
        try:
            soup = _get_soup(url)
        except Exception as e:
            print(f"[naijaremotejobs] fetch failed for '{kw}': {e}")
            continue

        # WordPress job listings are typically headline links inside
        # <h2>/<h3> tags on search/archive pages.
        candidates = soup.select("h1 a[href], h2 a[href], h3 a[href], article a[href]")
        count = 0
        seen_hrefs = set()
        for a in candidates:
            if count >= max_per_keyword:
                break
            href = a.get("href", "")
            if not href or href in seen_hrefs or "naijaremotejobs.com" not in href:
                continue
            title = _clean_text(a)
            if not title or len(title) < 6:
                continue
            if not _matches_keywords(title, keywords):
                continue
            seen_hrefs.add(href)

            jobs.append({
                "source": "NaijaRemoteJobs",
                "title": title,
                "company": "",
                "location": "Remote (Nigeria-friendly)",
                "url": href,
                "id": f"naijaremotejobs:{href}",
            })
            count += 1
        time.sleep(1)
    return jobs
