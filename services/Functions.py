
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