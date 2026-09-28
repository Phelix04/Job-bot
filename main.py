"""
Custom job search bot for Akin.

Run manually with:  python main.py
Runs automatically every 2 hours via .github/workflows/job-check.yml

What it does:
1. Reads config.json for keywords + which sources are turned on.
2. Fetches jobs from each enabled source.
3. Filters to jobs matching the keywords.
4. Drops jobs already sent before (tracked in seen_jobs.json).
5. Sends a Telegram message for each new match.
6. Saves the updated seen_jobs.json so the same job isn't sent twice.
"""
import json
import os
import sys
import requests

from sources.api_sources import (
    fetch_remoteok, fetch_arbeitnow, fetch_reliefweb, fetch_jobicy, fetch_remotive,
)
from sources.scrape_sources import fetch_jobberman, fetch_myjobmag, fetch_naijaremotejobs

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
SEEN_PATH = os.path.join(os.path.dirname(__file__), "seen_jobs.json")
MAX_SEEN_STORED = 3000  # keeps seen_jobs.json from growing forever


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen():
    if not os.path.exists(SEEN_PATH):
        return set()
    with open(SEEN_PATH, "r", encoding="utf-8") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()


def save_seen(seen_ids):
    trimmed = list(seen_ids)[-MAX_SEEN_STORED:]
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        print(f"[telegram] send failed ({resp.status_code}): {resp.text}")
    return resp.status_code == 200


def format_message(job):
    title = job["title"]
    company = job.get("company", "") or "Unknown company"
    location = job.get("location", "") or "Location not specified"
    source = job["source"]
    url = job["url"]
    return (
        f"<b>{escape_html(title)}</b>\n"
        f"{escape_html(company)} — {escape_html(location)}\n"
        f"Source: {escape_html(source)}\n"
        f"{url}"
    )


def escape_html(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main():
    config = load_config()
    token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")

    if not token or "PASTE_YOUR" in token:
        print("ERROR: telegram_bot_token is not set in config.json")
        sys.exit(1)
    if not chat_id or "PASTE_YOUR" in str(chat_id):
        print("ERROR: telegram_chat_id is not set in config.json")
        sys.exit(1)

    keywords = [k.lower() for k in config.get("keywords", [])]
    reliefweb_keywords = config.get("reliefweb_keywords", keywords)
    sources_enabled = config.get("sources", {})
    reliefweb_limit = config.get("reliefweb_limit_per_run", 20)
    reliefweb_appname = config.get("reliefweb_appname", "reliefweb-jobsearch-bot")
    jobicy_geos = config.get("jobicy_geos", ["anywhere", "australia", "apac", "emea", "latam"])
    remotive_location_keywords = [
        k.lower() for k in config.get(
            "remotive_location_keywords",
            ["worldwide", "anywhere", "africa", "nigeria", "emea", "middle east",
             "australia", "apac", "latam", "south america", "latin america"],
        )
    ]

    all_jobs = []

    if sources_enabled.get("remoteok", True):
        print("Checking RemoteOK...")
        all_jobs += fetch_remoteok(keywords)

    if sources_enabled.get("arbeitnow", True):
        print("Checking Arbeitnow...")
        all_jobs += fetch_arbeitnow(keywords)

    if sources_enabled.get("reliefweb", True):
        print("Checking ReliefWeb (WHO / UN / NGO jobs)...")
        all_jobs += fetch_reliefweb(reliefweb_keywords, limit=reliefweb_limit, appname=reliefweb_appname)

    if sources_enabled.get("jobicy", True):
        print("Checking Jobicy (remote-only, by region)...")
        all_jobs += fetch_jobicy(keywords, jobicy_geos)

    if sources_enabled.get("remotive", True):
        print("Checking Remotive (remote-only)...")
        all_jobs += fetch_remotive(keywords, remotive_location_keywords)

    if sources_enabled.get("jobberman", True):
        print("Checking Jobberman...")
        all_jobs += fetch_jobberman(keywords)

    if sources_enabled.get("myjobmag", True):
        print("Checking MyJobMag...")
        all_jobs += fetch_myjobmag(keywords)

    if sources_enabled.get("naijaremotejobs", True):
        print("Checking NaijaRemoteJobs...")
        all_jobs += fetch_naijaremotejobs(keywords)

    print(f"Total matches before dedup: {len(all_jobs)}")

    seen = load_seen()
    new_jobs = []
    for job in all_jobs:
        if job["id"] not in seen:
            new_jobs.append(job)
            seen.add(job["id"])

    print(f"New jobs to send: {len(new_jobs)}")

    sent_count = 0
    for job in new_jobs:
        ok = send_telegram_message(token, chat_id, format_message(job))
        if ok:
            sent_count += 1

    save_seen(seen)
    print(f"Done. Sent {sent_count} Telegram message(s).")


if __name__ == "__main__":
    main()
