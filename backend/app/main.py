from __future__ import annotations

import ipaddress
import os
import socket
import sqlite3
import time
from collections import deque
from contextlib import contextmanager
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.getenv("BHARATSEARCH_DB", "bharatsearch.db")
USER_AGENT = os.getenv("BHARATSEARCH_USER_AGENT", "BharatSearchBot/0.1 (+https://github.com/cryding/BharatSearch)")
MAX_RESPONSE_BYTES = 2_000_000
REQUEST_TIMEOUT = 10

app = FastAPI(title="BharatSearch API", version="0.1.0",
              description="Early-stage independent crawler and search index.")
origins = [x.strip() for x in os.getenv(
    "BHARATSEARCH_ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"
).split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"], allow_credentials=False)


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        # FTS5 is included in standard SQLite builds; fail clearly if unavailable.
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            url UNINDEXED, title, description, body, content='pages', content_rowid='id'
        )""")
        db.executescript("""
        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
          INSERT INTO pages_fts(rowid,url,title,description,body)
          VALUES(new.id,new.url,new.title,new.description,new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
          INSERT INTO pages_fts(pages_fts,rowid,url,title,description,body)
          VALUES('delete',old.id,old.url,old.title,old.description,old.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
          INSERT INTO pages_fts(pages_fts,rowid,url,title,description,body)
          VALUES('delete',old.id,old.url,old.title,old.description,old.body);
          INSERT INTO pages_fts(rowid,url,title,description,body)
          VALUES(new.id,new.url,new.title,new.description,new.body);
        END;
        """)


@app.on_event("startup")
def startup():
    init_db()


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=30)


class CrawlRequest(BaseModel):
    seed_urls: list[str] = Field(min_length=1, max_length=10)
    max_pages: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=1, ge=0, le=3)


def safe_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only absolute HTTP/HTTPS URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    host = parsed.hostname.lower()
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hostnames are not allowed.")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Hostname could not be resolved.") from exc
    for entry in addresses:
        ip = ipaddress.ip_address(entry[4][0])
        if not ip.is_global:
            raise ValueError("Private, loopback, link-local and reserved network targets are blocked.")
    return urldefrag(url)[0]


def fetch_page(url: str) -> tuple[str, str, str, list[str], str]:
    url = safe_public_http_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    # Disable automatic redirects; validate each redirect destination to reduce SSRF risk.
    current = url
    response = None
    for _ in range(4):
        response = requests.get(current, headers=headers, timeout=REQUEST_TIMEOUT,
                                stream=True, allow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("Redirect without a location.")
            current = safe_public_http_url(urljoin(current, location))
            continue
        break
    if response is None:
        raise ValueError("No response.")
    with response:
        if response.status_code >= 400:
            raise ValueError(f"HTTP status {response.status_code}")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ValueError("Not an HTML page.")
        chunks, size = [], 0
        for chunk in response.iter_content(16384):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ValueError("Page exceeds the 2 MB response limit.")
            chunks.append(chunk)
        raw = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        html = raw.decode(encoding, errors="replace")
        final_url = response.url or current
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        element.decompose()
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:500]
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", ""))[:1000] if meta else ""
    body = " ".join(soup.get_text(" ", strip=True).split())[:100_000]
    links = []
    for anchor in soup.find_all("a", href=True):
        candidate = urljoin(final_url, anchor["href"])
        parsed = urlparse(candidate)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            links.append(urldefrag(candidate)[0])
    return final_url, title, description, links, body


def robots_allowed(url: str) -> tuple[bool, float]:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        r = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=5,
                         allow_redirects=False)
        if r.status_code == 200:
            parser.parse(r.text.splitlines())
        elif r.status_code in (401, 403):
            return False, 5.0
        else:
            return True, 1.0
    except requests.RequestException:
        # Be conservative when robots.txt cannot be checked.
        return False, 5.0
    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 1
    return parser.can_fetch(USER_AGENT, url), min(max(float(delay), 1.0), 10.0)


@app.get("/health")
def health():
    return {"status": "ok", "service": "bharatsearch-api", "version": "0.1.0"}


@app.get("/api/stats")
def stats():
    with connection() as db:
        count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    return {"indexed_pages": count, "engine": "SQLite FTS5", "stage": "early-development"}


@app.get("/api/search")
def search(q: str, limit: int = 10):
    q = q.strip()
    if not q or len(q) > 200:
        raise HTTPException(400, "Enter a search query up to 200 characters.")
    limit = min(max(limit, 1), 30)
    # Quote tokens to avoid exposing raw FTS operators to user input.
    tokens = [token.replace('"', '""') for token in q.split() if token]
    match_query = " AND ".join(f'"{token}"' for token in tokens)
    if not match_query:
        return {"query": q, "results": []}
    try:
        with connection() as db:
            rows = db.execute("""
                SELECT p.url, p.title, p.description, snippet(pages_fts, 3, '<b>', '</b>', '…', 18) AS snippet
                FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid
                WHERE pages_fts MATCH ?
                ORDER BY bm25(pages_fts, 0, 8, 3, 1)
                LIMIT ?
            """, (match_query, limit)).fetchall()
    except sqlite3.OperationalError:
        return {"query": q, "results": []}
    return {"query": q, "results": [dict(row) for row in rows]}


@app.post("/api/crawl")
def crawl(request: CrawlRequest):
    queue = deque()
    for seed in request.seed_urls:
        try:
            queue.append((safe_public_http_url(seed), 0))
        except ValueError as exc:
            raise HTTPException(400, f"Invalid seed URL: {exc}") from exc
    seen: set[str] = set()
    crawled = 0
    skipped = 0
    last_host_request: dict[str, float] = {}
    while queue and crawled < request.max_pages:
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        allowed, delay = robots_allowed(url)
        if not allowed:
            skipped += 1
            continue
        wait = delay - (time.monotonic() - last_host_request.get(host, 0))
        if wait > 0:
            time.sleep(min(wait, 10))
        try:
            final_url, title, description, links, body = fetch_page(url)
            last_host_request[host] = time.monotonic()
            with connection() as db:
                db.execute("""INSERT INTO pages(url,title,description,body) VALUES(?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET title=excluded.title,
                    description=excluded.description, body=excluded.body,
                    crawled_at=CURRENT_TIMESTAMP""",
                    (final_url, title, description, body))
            crawled += 1
            if depth < request.max_depth:
                for link in links:
                    if link not in seen and len(queue) < 500:
                        # Keep traversal on the seed host to limit unintended crawl scope.
                        if urlparse(link).netloc.lower() == host:
                            queue.append((link, depth + 1))
        except (requests.RequestException, ValueError, UnicodeError):
            skipped += 1
    return {"crawled": crawled, "skipped": skipped, "visited": len(seen),
            "remaining_queue": len(queue), "note": "Bounded manual crawl; results depend on reachable pages and robots.txt."}
