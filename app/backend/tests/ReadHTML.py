import requests
import json

from bs4 import BeautifulSoup

cafe_id = "steamindiegame"
menu_id = "18763709"

# API 호출 예시
url = f"{NAVER_CAFE_}/{cafe_id}/articles/{menu_id}?useCafeId=false"

response = requests.get(url)
data = response.json()

# HTML 파싱
soup = BeautifulSoup(data['result']['article']['contentHtml'], 'html.parser')

# '__se_module_data' 클래스를 가진 모든 스크립트 태그 찾기
datas = soup.find_all(class_="__se_module_data")

youtube_links = []
for data in datas:
    # data-module 속성에서 JSON 데이터 추출
    module_data = data.get('data-module')
    if module_data:
        a = json.loads(module_data)['data']
        if a.get('html') is None:
            continue

        # HTML 내용에서 <iframe> 태그 추출
        iframe_html = a['html']
        iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
        iframe = iframe_soup.find('iframe')

        # src 속성 추출
        if iframe and 'src' in iframe.attrs:
            youtube_links.append(iframe['src'])

# 결과 출력
for link in youtube_links:
    print(link)