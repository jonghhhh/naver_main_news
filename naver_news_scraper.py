import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pytz
import json
import os
import sys
from github import Github, GithubException
import base64
import traceback

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
    """네이버 언론사 메인 뉴스 스크랩"""
    results = []
    
    # Get current time in KST
    utc_dt = datetime.utcnow()
    utc_dt_aware = pytz.utc.localize(utc_dt)
    kst_dt = utc_dt_aware.astimezone(pytz.timezone('Asia/Seoul'))
    timestamp = kst_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"===== {timestamp} 뉴스 스크래핑 시작 =====")
    
    for news_org, oid in press_oid_list.items():
        try:
            news_url = f"https://media.naver.com/press/{oid}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(news_url, headers=headers)
            
            if response.status_code != 200:
                print(f"error - {news_org} 응답 코드: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
            news_items = soup.select('a.press_news_link._es_pc_link')
            
            if not news_items:
                print(f"info - {news_org}에서 뉴스 항목을 찾을 수 없습니다.")
                continue
                
            for item in news_items:
                if 'main' in item.get('href', ''):
                    title_elements = item.select('span.press_news_text')
                    
                    if not title_elements:
                        continue
                        
                    title = title_elements[0].text.strip()
                    url = item['href']
                    
                    results.append({
                        "news_org": news_org,
                        "timestamp": timestamp,
                        "title": title,
                        "url": url
                    })
            
            print(f"success - {news_org}에서 {len([i for i in news_items if 'main' in i.get('href', '')])}개 항목 스크랩")
                    
        except Exception as e:
            print(f"error - {news_org} 스크래핑 중 오류: {str(e)}")
    
    print(f"===== 총 {len(results)}개 뉴스 항목 스크랩 완료 =====")
    return results

def safe_read_jsonl_file(repo, file_path):
    """안전하게 GitHub에서 JSONL 파일 읽기"""
    try:
        contents = repo.get_contents(file_path)
        print(f"debug - 파일 정보: 인코딩={contents.encoding}, 크기={len(contents.content) if contents.content else 0}")
        
        if contents.encoding == 'base64' and contents.content:
            try:
                content_string = base64.b64decode(contents.content).decode('utf-8')
                
                # JSONL 파일은 각 줄을 개별 JSON으로 파싱
                existing_data = []
                for line in content_string.splitlines():
                    if line.strip():  # 빈 줄 건너뛰기
                        try:
                            item = json.loads(line)
                            existing_data.append(item)
                        except json.JSONDecodeError:
                            print(f"warning - 줄 파싱 오류, 건너뜁니다: {line[:50]}...")
                
                print(f"success - JSONL 파일에서 {len(existing_data)}개 항목을 불러왔습니다.")
                return existing_data, contents.sha
                
            except Exception as e:
                print(f"error - 파일 디코딩 오류: {str(e)}")
                return [], contents.sha
        else:
            print(f"warning - 지원되지 않는 파일 인코딩: {contents.encoding}")
            return [], contents.sha
            
    except GithubException as e:
        if e.status == 404:
            print(f"info - {file_path} 파일이 존재하지 않습니다.")
        else:
            print(f"error - GitHub API 오류: 상태={e.status}, 데이터={e.data}")
        return [], None
        
    except Exception as e:
        print(f"error - 파일 읽기 중 일반 오류: {str(e)}")
        traceback.print_exc()
        return [], None

def convert_to_jsonl(data_list):
    """데이터 리스트를 JSONL 문자열로 변환"""
    jsonl_lines = []
    for item in data_list:
        jsonl_lines.append(json.dumps(item, ensure_ascii=False))
    return '\n'.join(jsonl_lines)

def update_github_jsonl(data):
    """새 데이터를 GitHub 저장소의 JSONL 파일에 추가"""
    if not data:
        print("warning - 추가할 데이터가 없습니다.")
        return True
    
    # GitHub 인증 및 설정
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("error - GITHUB_TOKEN 환경변수가 설정되지 않았습니다!")
        return False
        
    repo_name = 'jonghhhh/naver_main_news'
    file_path = 'naver_main_news_040825.jsonl'  # 확장자를 jsonl로 변경
    
    print(f"===== GitHub 저장소 '{repo_name}' 업데이트 시작 =====")
    
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        
        # 1. 기존 파일 읽기 시도
        existing_data, sha = safe_read_jsonl_file(repo, file_path)
        
        # 2. 새 데이터 추가
        combined_data = existing_data + data
        
        # 3. JSONL 형식으로 변환 (각 항목을 한 줄에 저장)
        jsonl_content = convert_to_jsonl(combined_data)
        
        # 4. 파일 업데이트 또는 생성
        if sha:
            try:
                commit_result = repo.update_file(
                    file_path,
                    f"Update news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    jsonl_content,
                    sha
                )
                print(f"success - 파일이 업데이트되었습니다. 커밋 SHA: {commit_result['commit'].sha}")
            except Exception as e:
                print(f"error - 파일 업데이트 중 오류: {str(e)}")
                traceback.print_exc()
                return False
        else:
            try:
                commit_result = repo.create_file(
                    file_path,
                    f"Initial news data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    jsonl_content
                )
                print(f"success - 새 파일이 생성되었습니다. 커밋 SHA: {commit_result['commit'].sha}")
            except Exception as e:
                print(f"error - 파일 생성 중 오류: {str(e)}")
                traceback.print_exc()
                return False
        
        print(f"===== GitHub 저장소 업데이트 완료 (총 {len(combined_data)}개 항목) =====")
        return True
        
    except Exception as e:
        print(f"error - GitHub 처리 중 예상치 못한 오류: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(f"\n\n===== 네이버 뉴스 스크래퍼 시작 ({datetime.now()}) =====")
    print(f"Python 버전: {sys.version}")
    print(f"실행 경로: {os.getcwd()}")
    
    # 1. 환경 변수 확인
    if not os.environ.get('GITHUB_TOKEN'):
        print("error - GITHUB_TOKEN 환경변수가 설정되지 않았습니다!")
        exit(1)
    
    # 2. 뉴스 스크랩
    news_data = scrape_naver_news()
    
    if not news_data:
        print("warning - 수집된 뉴스 데이터가 없습니다. 종료합니다.")
        exit(0)
    
    # 3. GitHub 저장소 업데이트 (JSONL 형식으로)
    success = update_github_jsonl(news_data)
    
    if success:
        print(f"===== 프로그램 정상 종료 - {len(news_data)}개 뉴스 항목 처리됨 =====")
        exit(0)
    else:
        print(f"===== 프로그램 오류 종료 - GitHub 저장소 업데이트 실패 =====")
        # 크론잡 오류로 표시되도록 1로 종료
        exit(1)
