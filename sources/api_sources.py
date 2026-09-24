"""
Job sources that use official, public JSON APIs. These are the most
reliable sources in the bot because they can't be broken by a site
redesign the way HTML scraping can.
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AkinJobBot/1.0)"}
TIMEOUT = 20


def fetch_remoteok(keywords):
    """RemoteOK public API: https://remoteok.com/api
    Returns remote jobs worldwide. First item in the response is a
    legal/notice object, not a job, so it's skipped.
    """
    jobs = []
    try:
        resp = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[remoteok] fetch failed: {e}")
        return jobs

    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue  # skips the legal notice entry
        title = item.get("position", "")
        company = item.get("company", "")
        description = item.get("description", "") or ""
        tags = " ".join(item.get("tags", []) or [])
        haystack = f"{title} {description} {tags}".lower()

        if any(kw in haystack for kw in keywords):
            jobs.append({
                "source": "RemoteOK",
                "title": title,
                "company": company,
                "location": item.get("location", "Remote") or "Remote",
                "url": item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
                "id": f"remoteok:{item.get('id', item.get('slug', title))}",
            })
    return jobs


def fetch_arbeitnow(keywords):
    """Arbeitnow public API: https://arbeitnow.com/api/job-board-api"""
    jobs = []
    try:
        resp = requests.get(
            "https://arbeitnow.com/api/job-board-api", headers=HEADERS, timeout=TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        print(f"[arbeitnow] fetch failed: {e}")
        return jobs

    for item in data:
        title = item.get("title", "")
        description = item.get("description", "") or ""
        tags = " ".join(item.get("tags", []) or [])
        haystack = f"{title} {description} {tags}".lower()

        if any(kw in haystack for kw in keywords):
            jobs.append({
                "source": "Arbeitnow",
                "title": title,
                "company": item.get("company_name", ""),
                "location": item.get("location") or ("Remote" if item.get("remote") else ""),
                "url": item.get("url", ""),
                "id": f"arbeitnow:{item.get('slug', title)}",
            })
    return jobs


def fetch_reliefweb(keywords, limit=20):
    """ReliefWeb public API - the official aggregator for WHO, UN agencies,
    and international NGO vacancies. Docs: https://apidoc.reliefweb.int/
    One request per keyword phrase (ReliefWeb doesn't OR multi-phrase
    queries reliably), deduped by job id afterwards.
    """
    jobs = []
    seen_ids = set()
    base_url = "https://api.reliefweb.int/v1/jobs"

    for kw in keywords:
        params = {
            "appname": "akin-jobsearch-bot",
            "query[value]": kw,
            "query[fields][]": "title",
            "limit": limit,
            "sort[]": "date.created:desc",
            "fields[include][]": ["title", "url", "date.created", "source.name", "country.name"],
        }
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[reliefweb] fetch failed for '{kw}': {e}")
            continue

        for item in data.get("data", []):
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            fields = item.get("fields", {})
            title = fields.get("title", "")
            url = fields.get("url", "")
            sources = fields.get("source", [])
            source_name = sources[0].get("name") if sources else "ReliefWeb"
            countries = fields.get("country", [])
            country_name = countries[0].get("name") if countries else ""

            jobs.append({
                "source": f"ReliefWeb ({source_name})",
                "title": title,
                "company": source_name,
                "location": country_name,
                "url": url,
                "id": f"reliefweb:{item_id}",
            })
    return jobs
