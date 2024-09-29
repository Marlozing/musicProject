import time

import soundfile
from pytubefix import YouTube
from selenium import webdriver
import csv
from bs4 import BeautifulSoup as bs
from selenium.webdriver.common.by import By
from moviepy.editor import *
import os
import numpy as np
import librosa

from findStartTime import find_time

def clear_folder(path):
  for filename in os.listdir(path):
    file_path = os.path.join(path, filename)
    if os.path.isfile(file_path):  # 파일인지 확인
      os.remove(file_path)  # 파일 삭제
def convert_oembed_link_to_youtube_url(oembed_link):
  # 임베디드된 주소에서 유튜브 비디오의 고유 ID 추출
  video_id = oembed_link.split("/")[-1].split("?")[0]

  # 실행 가능한 유튜브 주소로 변환
  watch_url = f"https://www.youtube.com/watch?v={video_id}"

  return watch_url

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

def get_viewer(author, title):
  # wav 파일로 변환하여 저장
  list = ["우왁굳","아이네","징버거","릴파","주르르","고세구","비챤","뢴트게늄"]
  authors = {"우왁굳의 계륵": "[우왁굳]", "데친 숙주나물": "[아이네]", "징버거가 ZZANG센 주제에 너무 신중하다": "[징버거]", "릴파의 순간들": "[릴파]",
             "주르르": "[주르르]", "고세구의 짧은거": "[고세구]", "비챤의 나랑놀아": "[비챤]", "하치키타치": "[뢴트게늄]"}
  wav_path = "원본"
  for i in list:
      if author == "반응정리":
        if i in title.split(" ")[0]:
          wav_path = title.split(" ")[0]
  for i in authors:
      if author == i:
          wav_path = authors[i]

  return wav_path

f = open('crawl.csv', 'r', encoding="utf-8")
rdr = csv.reader(f)
num = 0
for line in rdr:
  if line[0] == "제목":
      continue
  num += 1
  print(str(num) + ". " + line[0])
select = int(input("원하는 영상 숫자를 골라주세요 "))

clear_folder('./video')
clear_folder('./audio')

f.close()
f = open('crawl.csv', 'r', encoding="utf-8")
rdr = csv.reader(f)
num = 0
for line in rdr:
  if select == num:
      url = line[1]
  num += 1
browser = login("ipindong", "Jet2033050!")
browser.get("https://cafe.naver.com" + url)

time.sleep(2)

browser.switch_to.frame('cafe_main')
soup = bs(browser.page_source, 'html.parser')
datas = soup.find_all(class_='se-component se-oembed se-l-default __se-component')
num = 0

youtube_links = []
for data in datas:
  num += 1
  data = data.find_all_next(class_='__se_module_data')[0]
  youtubeLink = str(data).split("src=")[1].split('"')[1].replace("\\","")
  watch_url = convert_oembed_link_to_youtube_url(youtubeLink)
  youtube_links.append(watch_url)
browser.quit()  # 브라우저 종료

download_path = './video'
origin = np.array([])

RES = '2160p'

for link in youtube_links:
  yt = YouTube(link)
  title = yt.title
  title = get_viewer(yt.author, title)

  if not os.path.exists(download_path):
    os.makedirs(download_path)

  stream = yt.streams.get_highest_resolution()
  stream.download(output_path=download_path,filename=title+".mp4")
  mp4_path = download_path+"/"+title+".mp4"
  audio_clip = AudioFileClip(mp4_path)
  audio_clip.write_audiofile("audio/"+title+".wav")

origin, _ = librosa.load("./audio/원본.wav")
for filename in os.listdir('./audio'):
  y, sr = librosa.load("./audio/"+filename)
  # y의 앞에 패딩 하기
  y = np.pad(y, (sr*1, 0), 'constant')
  if filename != "원본.wav":
    start_index = find_time(origin, y) * 512
    soundfile.write("./audio/"+filename, y[start_index:],sr)

print('작업 완료')
