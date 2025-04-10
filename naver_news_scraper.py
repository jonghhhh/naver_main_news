import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pytz
import json
import os
from github import Github, GithubException
import base64

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

def get_existing_data(repo, file_path):
    """GitHub 저장소에서 기존 JSON 데이터 가져오기"""
    try:
        # API를 통해 파일 내용 가져오기
        contents = repo.get_contents(file_path)
        
        # base64 인코딩인 경우만 처리
        if contents.encoding == 'base64':
            content_string = base64.b64decode(contents.content).decode('utf-8')
            try:
                existing_data = json.loads(content_string)
                print(f"기존 파일에서 {len(existing_data)}개의 데이터를 불러왔습니다.")
                return existing_data, contents.sha
            except json.JSONDecodeError:
                print("파일이 유효한 JSON 형식이 아닙니다. 빈 배열로 시작합니다.")
                return [], contents.sha
        else:
            print(f"파일의 인코딩이 지원되지 않습니다: {contents.encoding}")
            return [], None
            
    except GithubException as e:
        if e.status == 404:
            print("파일이 존재하지 않습니다. 새로 생성합니다.")
        else:
            print(f"GitHub API 오류: {e.data}")
        return [], None
        
    except Exception as e:
        print(f"파일 읽기 중 오류 발생: {str(e)}")
        return [], None

def update_github_json(data):
    """새 데이터를 GitHub 저장소에 추가 (기존 데이터 유지)"""
    if not data:
        print("추가할 데이터가 없습니다.")
        return True
        
    # GitHub 인증
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = 'jonghhhh/naver_main_news'
    file_path = 'naver_main_news_040825.json'
    
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    
    try:
        # 기존 데이터 가져오기
        existing_data, sha = get_existing_data(repo, file_path)
        
        # 새 데이터 추가
        combined_data = existing_data + data
        
        # JSON 문자열로 변환
        json_content = json.dumps(combined_data, ensure_ascii=False, indent=2)
        
        if sha:
            # 파일이 이미 존재하면 업데이트
            repo.update_file(
                file_path,
                f"Update news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                json_content,
                sha
            )
            print(f"기존 파일을 업데이트했습니다. 이제 총 {len(combined_data)}개의 항목이 있습니다.")
        else:
            # 파일이 없으면 새로 생성
            repo.create_file(
                file_path,
                f"Initial news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                json_content
            )
            print(f"새 파일을 생성했습니다. {len(data)}개의 항목이 있습니다.")
        
        return True
        
    except Exception as e:
        print(f"GitHub 업데이트 중 오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    # 뉴스 스크랩
    news_data = scrape_naver_news()
    
    if not news_data:
        print("수집된 뉴스 데이터가 없습니다. 종료합니다.")
        exit(0)
    
    # GitHub 저장소 업데이트
    success = update_github_json(news_data)
    
    if success:
        print(f"성공적으로 {len(news_data)}개의 뉴스 항목을 스크랩하고 GitHub 저장소를 업데이트했습니다.")
    else:
        print(f"GitHub 저장소 업데이트에 실패했습니다.")
        # 실패 시에도 프로그램은 정상 종료되어야 크론잡 오류가 발생하지 않습니다
        exit(0)  # 0으로 종료하여 크론잡 오류 방지
