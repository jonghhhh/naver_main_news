import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pytz
import json
import os
from github import Github

# Naver press OID dictionary
press_oid_list = {
    '조선일보': '023', '중앙일보': '025', '동아일보': '020', 
    '한겨레': '028', '경향신문': '032', '오마이뉴스': '047', 
    'KBS': '056', 'MBC': '214', 'SBS': '055', 
    'TV조선': '448', 'JTBC': '437', '채널A': '449', 'MBN': '057',
    '연합뉴스': '001', 'YTN': '052', '국민일보': '005', '한국일보': '469', 
    '매일경제': '009', '한국경제': '015', '아시아경제': '277', '부산일보': '082', 
    '전주MBC': '659', 'KBC광주방송': '660', '대전일보': '656', 'CJB청주방송': '655', 
    '강원도민일보': '654', '대구MBC': '657', 'JIBS': '661'
}

def scrape_naver_news():
    results = []
    
    # Get current time in KST
    utc_dt = datetime.utcnow()
    utc_dt_aware = pytz.utc.localize(utc_dt)
    kst_dt = utc_dt_aware.astimezone(pytz.timezone('Asia/Seoul'))
    timestamp = kst_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    for news_org, oid in press_oid_list.items():
        try:
            news_url = f"https://media.naver.com/press/{oid}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(news_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
            news_items = soup.select('a.press_news_link._es_pc_link')
            for item in news_items:
                if 'main' in item.get('href', ''):
                    title = item.select('span.press_news_text')[0].text.strip()
                    url = item['href']
                    
                    results.append({
                        "news_org": news_org,
                        "timestamp": timestamp,
                        "title": title,
                        "url": url
                    })
                    
        except Exception as e:
            print(f"Error scraping {news_org}: {e}")
    
    return results

def update_github_json(data):
    # GitHub authentication
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('jonghhhh/naver_main_news')
    file_path = 'naver_main_news_040825.json'
    
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        # Try to get the existing file
        file_content = repo.get_contents(file_path)
        existing_data = json.loads(file_content.decoded_content.decode())
        
        # Append new data
        combined_data = existing_data + data
        
        # Update file in repository
        repo.update_file(
            file_path,
            f"Update news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            json.dumps(combined_data, ensure_ascii=False, indent=2),
            file_content.sha
        )
    except:
        # If file doesn't exist, create it
        repo.create_file(
            file_path,
            f"Initial news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            json.dumps(data, ensure_ascii=False, indent=2)
        )

if __name__ == "__main__":
    # Scrape the news
    news_data = scrape_naver_news()
    
    # Update the GitHub repository
    update_github_json(news_data)
    
    print(f"Successfully scraped {len(news_data)} news items and updated GitHub repo.")
