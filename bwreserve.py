import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

BASE_URL = "https://bookwalker.jp/schedule/?qsto=st1&qpri=2&np=1&detail=0&page={page}"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Referer': 'https://bookwalker.jp/',
    'Cache-Control': 'no-cache'
}

# Helper to extract reserve count
def get_reserve_count(book_url, session):
    try:
        time.sleep(random.uniform(1.0, 2.0))
        response = session.get(book_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        reserve_tag = soup.select_one("#js-read-check > div.t-c-detail-main__book > div > p > em")
        reserve = None
        if reserve_tag:
            reserve_text = reserve_tag.text.strip().replace("人", "")
            reserve = int(reserve_text) if reserve_text.isdigit() else None

        # Get release date
        release_date = "Unknown"
        dl_tag = soup.select_one("section.t-c-detail-about-information > dl")
        if dl_tag:
            dt_tags = dl_tag.find_all("dt")
            dd_tags = dl_tag.find_all("dd")
            for dt, dd in zip(dt_tags, dd_tags):
                if "配信開始日" in dt.text:
                    release_date = dd.text.strip()
                    break

        return reserve, release_date
    except Exception as e:
        print(f"Error getting reserve count for {book_url}: {e}")
        return None, "Unknown"

def scrape_page(page, session):
    url = BASE_URL.format(page=page)
    print(f"Scraping page: {url}")
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        books = []

        for x in range(1, 61):
            selector = f"#pageWrapInner > div.t-contents > div.t-contents-inner > div > section > div.o-contents-section__body > ul > li:nth-child({x}) > div > div.m-book-item__info-block > div.m-book-item__secondary > p.m-book-item__title > a"
            book_element = soup.select_one(selector)
            if not book_element:
                continue

            title = book_element.text.strip()
            url = book_element['href']
            if url.startswith('/'):
                url = "https://bookwalker.jp" + url
            books.append({'title': title, 'url': url})

        return books
    except Exception as e:
        print(f"Failed to scrape page {page}: {e}")
        return []

def scrape_all_books():
    all_books = []
    page = 1
    session = requests.Session()
    session.headers.update(HEADERS)

    while True:
        books = scrape_page(page, session)
        if not books:
            break
        all_books.extend(books)
        page += 1
        time.sleep(random.uniform(1.0, 2.0))

    today = str(date.today())
    print(f"Scraping day {today}")

    results = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for book in all_books:
            futures.append(executor.submit(scrape_book_data, book, session, today))

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return results

def scrape_book_data(book, session, today):
    try:
        reserve, release_date = get_reserve_count(book['url'], session)

        try:
            if release_date != "Unknown":
                release_dt = datetime.strptime(release_date, "%Y/%m/%d").date()
                if release_dt <= date.today():
                    print(f"Skipping released book: {book['title']}")
                    return None
        except Exception as e:
            print(f"Date parse error for {book['title']}: {e}")

        response = session.get(book['url'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')

        ld_data = json.loads(script_tag.string) if script_tag else {}

        return {
            'name': ld_data.get('name', None),
            'url': book['url'],
            'image': ld_data.get('image', None),
            'description': ld_data.get('description', None),
            'release_date': release_date,
            'reserve': {today: reserve}
        }
    except Exception as e:
        print(f"Error scraping book detail {book['url']}: {e}")
        return {
            'name': None,
            'url': book['url'],
            'image': None,
            'description': None,
            'release_date': None,
            'reserve': {today: None}
        }

def merge_with_existing(new_data, filename='bookwalker_output.json'):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

        existing_map = {book['url']: book for book in existing_data}

        for new_book in new_data:
            url = new_book['url']
            if url in existing_map:
                old_book = existing_map[url]
                old_reserve = old_book.get('reserve', {})
                new_reserve = new_book.get('reserve', {})
                old_reserve.update(new_reserve)
                old_book['reserve'] = old_reserve
                old_book.update({
                    'name': new_book.get('name', old_book.get('name')),
                    'image': new_book.get('image', old_book.get('image')),
                    'description': new_book.get('description', old_book.get('description')),
                    'release_date': new_book.get('release_date', old_book.get('release_date')),
                })
            else:
                existing_map[url] = new_book

        return list(existing_map.values())
    else:
        return new_data


def save_to_json(data, filename='bookwalker_output.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    scraped_books = scrape_all_books()
    merged_books = merge_with_existing(scraped_books)
    save_to_json(merged_books)
    print(f"Finished. Total books tracked: {len(merged_books)}")
