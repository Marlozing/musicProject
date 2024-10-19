
import os
import time
import librosa
import numpy as np
import soundfile
from selenium import webdriver
from selenium.webdriver.common.by import By

def login(id, pw):
  """
  네이버 로그인 함수
  주어진 ID와 비밀번호를 사용하여 네이버에 로그인합니다.
  """
  url = 'https://nid.naver.com/nidlogin.login'

  options = webdriver.ChromeOptions()
  options.add_argument("disable-gpu")  # GPU 가속 비활성화
  options.add_argument('headless')

  # Chrome 브라우저 인스턴스 생성
  browser = webdriver.Chrome(options=options)
  browser.get(url)  # 로그인 페이지 열기
  browser.implicitly_wait(2)  # 로드 대기

  # 로그인
  browser.execute_script("document.getElementsByName('id')[0].value=\'" + id + "\'")  # ID 입력
  browser.execute_script("document.getElementsByName('pw')[0].value=\'" + pw + "\'")  # 비밀번호 입력
  browser.find_element(by=By.XPATH, value='//*[@id="log.login"]').click()  # 로그인 버튼 클릭
  time.sleep(1)  # 잠시 대기

  return browser  # 브라우저 인스턴스 반환


def clear_folder(path):
  """
  폴더를 정리하는 함수
  지정된 경로의 폴더가 없으면 생성하고,
  존재하는 경우 모든 파일을 삭제합니다.
  """
  if not os.path.exists(path):
    os.makedirs(path)  # 폴더가 없으면 생성
    return
  for filename in os.listdir(path):
    file_path = os.path.join(path, filename)
    if os.path.isfile(file_path):
      os.remove(file_path)  # 파일 삭제


def change_to_youtube_url(source):
  """
  임베디드 링크에서 유튜브 URL로 변환
  주어진 oembed 링크에서 비디오 ID를 추출하여
  실행 가능한 유튜브 주소를 반환합니다.
  """
  video_id = str(source).split("src=")[1].split('"')[1].replace("\\", "").split("/")[-1].split("?")[0]  # 비디오 ID 추출
  return f"https://www.youtube.com/watch?v={video_id}"  # 유튜브 URL 반환


def get_viewer(author, title):
  """
  작성자 및 제목에 따라 WAV 파일 경로 결정
  주어진 작성자와 제목을 기반으로 WAV 파일의 경로를 결정합니다.
  """
  names = ["우왁굳", "아이네", "징버거", "릴파", "주르르", "고세구", "비챤", "뢴트게늄"]
  authors = {
    "우왁굳의 반찬가게": "[우왁굳]",
    "데친 숙주나물": "[아이네]",
    "징버거가 ZZANG센 주제에 너무 신중하다": "[징버거]",
    "릴파의 순간들": "[릴파]",
    "주르르": "[주르르]",
    "고세구의 짧은거": "[고세구]",
    "비챤의 나랑놀아": "[비챤]",
    "하치키타치": "[뢴트게늄]"
  }
  wav_path = "원본"  # 기본 경로

  # 작성자가 "반응정리"인 경우
  if author == "반응정리":
    for name in names:
      if name in title.split(" ")[0]:  # 제목의 첫 단어와 비교
        wav_path = title.split(" ")[0]  # 첫 단어를 경로로 설정

  # 작성자에 따른 경로 설정
  if author in authors:
    wav_path = authors[author]

  return wav_path  # 최종 경로 반환

def open_folder(folder_path):
  """파일을 열기 위한 함수"""
  try:
    if sys.platform == "win32":  # Windows
      os.startfile(folder_path)
    elif sys.platform == "darwin":  # macOS
      os.system(f'open "{folder_path}"')
    else:  # Linux 및 기타
      os.system(f'xdg-open "{folder_path}"')  # 대부분의 Linux 배포판에서 사용
  except Exception as e:
    print(f"Error opening file: {e}")