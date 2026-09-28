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


def fetch_reliefweb(keywords, limit=20, appname="reliefweb-jobsearch-bot"):
    """ReliefWeb public API - the official aggregator for WHO, UN agencies,
    and international NGO vacancies. Docs: https://apidoc.reliefweb.int/
    Uses API v2 (v1 was retired/deprecated by ReliefWeb and now returns
    HTTP 410 Gone; v2 uses the same query format).

    Note: since 1 Nov 2025 ReliefWeb asks API users to request a
    pre-approved "appname" (a short form on their site, reviewed within
    a business day). If requests here start failing with 403 Forbidden,
    request one at https://apidoc.reliefweb.int/ and put it in
    config.json under "reliefweb_appname" - no code changes needed.

    One request per keyword phrase (ReliefWeb doesn't OR multi-phrase
    queries reliably), deduped by job id afterwards.
    """
    jobs = []
    seen_ids = set()
    base_url = "https://api.reliefweb.int/v2/jobs"

    for kw in keywords:
        params = {
            "appname": appname,
            "query[value]": kw,
            "query[fields][]": "title",
            "limit": limit,
            "sort[]": "date.created:desc",
            "fields[include][]": ["title", "url", "date.created", "source.name", "country.name"],
        }
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                # Print ReliefWeb's actual error body, not just the status
                # code - it usually explains the real reason (unapproved
                # appname vs IP restriction vs something else).
                print(f"[reliefweb] HTTP {resp.status_code} for '{kw}'. Response body: {resp.text[:500]}")
                continue
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


def fetch_jobicy(keywords, geos, count=100):
    """Jobicy public API (free, no key): https://jobicy.com/api/v2/remote-jobs
    Every listing is remote. One request per region ("geo" slug, e.g.
    anywhere, australia, apac, emea, latam), then filtered by our
    keywords locally. To see all valid region slugs, open:
    https://jobicy.com/api/v2/remote-jobs?get=locations
    """
    jobs = []
    seen_ids = set()
    for geo in geos:
        params = {"count": count, "geo": geo}
        try:
            resp = requests.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params=params, headers=HEADERS, timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"[jobicy] HTTP {resp.status_code} for geo '{geo}'. Response body: {resp.text[:300]}")
                continue
            data = resp.json()
        except Exception as e:
            print(f"[jobicy] fetch failed for geo '{geo}': {e}")
            continue

        for item in data.get("jobs", []) or []:
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            title = item.get("jobTitle", "") or ""
            haystack = " ".join([
                title,
                str(item.get("jobExcerpt", "") or ""),
                str(item.get("jobIndustry", "") or ""),
            ]).lower()
            if not any(kw in haystack for kw in keywords):
                continue
            seen_ids.add(item_id)

            job_geo = item.get("jobGeo", geo)
            if isinstance(job_geo, list):
                job_geo = ", ".join(str(g) for g in job_geo)

            jobs.append({
                "source": "Jobicy (remote)",
                "title": title,
                "company": item.get("companyName", "") or "",
                "location": f"Remote - {job_geo}" if job_geo else "Remote",
                "url": item.get("url", ""),
                "id": f"jobicy:{item_id}",
            })
    return jobs


def fetch_remotive(keywords, location_keywords=None):
    """Remotive public API (free, no key): https://remotive.com/api/remote-jobs
    Every listing is remote. Remotive's server-side search/category
    filters currently don't filter anything, so this downloads the feed
    once and filters locally. Remotive asks that third parties link back
    to the original posting and credit Remotive (we do both), and that
    the feed isn't polled too frequently (one request per run is fine).

    location_keywords: optional list like ["worldwide", "africa", "emea"].
    Jobs restricted to a place that matches none of them (e.g. "USA
    Only") are skipped. Jobs with no location restriction are kept.
    """
    jobs = []
    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"[remotive] HTTP {resp.status_code}. Response body: {resp.text[:300]}")
            return jobs
        data = resp.json()
    except Exception as e:
        print(f"[remotive] fetch failed: {e}")
        return jobs

    for item in data.get("jobs", []) or []:
        title = item.get("title", "") or ""
        location = (item.get("candidate_required_location") or "").strip()

        if location_keywords and location:
            if not any(lk in location.lower() for lk in location_keywords):
                continue

        tags = " ".join(item.get("tags", []) or [])
        haystack = " ".join([
            title,
            str(item.get("category", "") or ""),
            tags,
            str(item.get("description", "") or ""),
        ]).lower()
        if not any(kw in haystack for kw in keywords):
            continue

        jobs.append({
            "source": "Remotive",
            "title": title,
            "company": item.get("company_name", "") or "",
            "location": f"Remote - {location}" if location else "Remote",
            "url": item.get("url", ""),
            "id": f"remotive:{item.get('id', title)}",
        })
    return jobs
