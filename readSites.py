import time
from selenium import webdriver
import csv
import pandas as pd
from bs4 import BeautifulSoup as bs
from selenium.webdriver.common.by import By

total_list = ["제목", "링크"]

f = open('crawl.csv', 'w', encoding="utf-8", newline='')
wr = csv.writer(f)
wr.writerow([total_list[0], total_list[1]])
f.close()
i = 0

def login(id, pw):
  # 네이버 로그인 url
  url = 'https://nid.naver.com/nidlogin.login'

  browser = webdriver.Chrome()
  browser.get(url)
  browser.implicitly_wait(2)

  # 로그인
  browser.execute_script("document.getElementsByName('id')[0].value=\'" + id + "\'")
  browser.execute_script("document.getElementsByName('pw')[0].value=\'" + pw + "\'")
  browser.find_element(by=By.XPATH, value='//*[@id="log.login"]').click()
  time.sleep(1)

  return browser
#while (True):
for j in range(2):
  origin_df = pd.read_csv('crawl.csv', encoding='utf-8')

  browser = login("ipindong", "Jet2033050!")

  # 크롤링 하고자하는 url
  baseurl = 'https://cafe.naver.com/ca-fe/cafes/27842958/members/X4X7z5aOcioCbe1qI-E8UVLKwmBlKET9fovk6zfnmPY?page='

  i = i + 1
  pageNum = i
  print(pageNum)
  browser.get(baseurl + str(pageNum))

  time.sleep(2)

  soup = bs(browser.page_source, 'html.parser')
  soup = soup.find_all(class_='article-board article_profile')[0]  # 네이버 카페 구조 확인후 게시글 내용만 가저오기

  datas = soup.select("table > tbody > tr")
  for data in datas:
      article_title = data.find(class_="article")
      link = article_title.get('href')

      if article_title is None:
          article_title = "null"
      else:
          article_title = article_title.get_text().strip()

      if article_title.__contains__("했어요]"):
          title_list = article_title.split("] ")
          article_title = title_list[-1].replace(" 반응정리", "")

          f = open('crawl.csv', 'a+', newline='', encoding="utf-8")  # 문자 인코딩 -> euc-kr 형태로 변경하여 사용. 안되면 utf-8로 변경 후 진행
          wr = csv.writer(f)

          wr.writerow([article_title, link])
          f.close()

print('종료\n\n\n')