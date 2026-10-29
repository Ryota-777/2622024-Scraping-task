import csv
import time
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

START_URL = "https://www.musashino-u.ac.jp/"
OUTPUT_CSV = "sitemap.csv"
SLEEP_SEC = 1.0          # 1リクエストごとの待機秒数(短くしすぎない)
TIMEOUT_SEC = 10
MAX_PAGES = None     # 動作確認時は 20 などにすると安全。None で無制限
USER_AGENT = "Mozilla/5.0 (university-scraping-task; student)"

# HTMLではないファイルは取得しない
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".mp4", ".mp3",
    ".css", ".js", ".ico", ".xml",
)


def normalize(url):
    """フラグメント(#以降)を除去してURLを正規化する"""
    url, _ = urldefrag(url)
    return url


def is_target(url, domain):
    """同一ドメインのhttp(s)で、HTMLらしきURLか判定する"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc != domain:
        return False
    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return False
    return True


def get_title(soup):
    """<title>タグの文字列を返す(なければ空文字)"""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def crawl(start_url):
    domain = urlparse(start_url).netloc

    # robots.txt を確認
    robots = RobotFileParser()
    robots.set_url(urljoin(start_url, "/robots.txt"))
    try:
        robots.read()
    except Exception:
        robots = None
    time.sleep(SLEEP_SEC)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    sitemap = {}                       # key: URL, value: title
    visited = set()
    queue = deque([normalize(start_url)])

    while queue:
        if MAX_PAGES is not None and len(sitemap) >= MAX_PAGES:
            break

        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if robots and not robots.can_fetch(USER_AGENT, url):
            print(f"[skip: robots.txt] {url}")
            continue

        try:
            response = session.get(url, timeout=TIMEOUT_SEC)
        except requests.RequestException as e:
            print(f"[error] {url} : {e}")
            time.sleep(SLEEP_SEC)
            continue
        finally:
            pass

        # 負荷軽減:リクエストのたびに必ず待機
        time.sleep(SLEEP_SEC)

        content_type = response.headers.get("Content-Type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            print(f"[skip: {response.status_code} {content_type}] {url}")
            continue

        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        sitemap[url] = get_title(soup)
        print(f"[{len(sitemap)}] {url} : {sitemap[url]}")

        # 同一ドメインのリンクをキューに追加
        for a in soup.find_all("a", href=True):
            link = normalize(urljoin(url, a["href"]))
            if link not in visited and is_target(link, domain):
                queue.append(link)

    return sitemap


def save_csv(sitemap, path):
    # utf-8-sig: Excelで開いても文字化けしにくい
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "title"])
        for url, title in sitemap.items():
            writer.writerow([url, title])


def main():
    sitemap = crawl(START_URL)
    save_csv(sitemap, OUTPUT_CSV)
    print(f"完了: {len(sitemap)} ページを {OUTPUT_CSV} に保存しました")


if __name__ == "__main__":
    main()