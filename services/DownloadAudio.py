import time
import csv
import librosa
import tkinter as tk
import numpy as np
import soundfile
import os

from pytubefix import YouTube
from moviepy.editor import AudioFileClip
from tkinter import ttk
from tkinter import messagebox as msgbox
from bs4 import BeautifulSoup as bs

from Functions import login
from FindStartTime import find_time

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


class DownloadAudio:
  def __init__(self, id, pw):
    self.id = id
    self.pw = pw
    self.url = None


  def read_cafe(self, length=1):
    total_list = ["제목", "링크"]

    with open('../datas/crawl.csv', 'w', encoding="utf-8", newline='') as f:
      wr = csv.writer(f)
      wr.writerow([total_list[0], total_list[1]])

    for i in range(1, length + 1):
      browser = login(self.id, self.pw)

      # 크롤링 하고자하는 url
      baseurl = 'https://cafe.naver.com/ca-fe/cafes/27842958/members/X4X7z5aOcioCbe1qI-E8UVLKwmBlKET9fovk6zfnmPY?page='
      browser.get(baseurl + str(i))

      time.sleep(2)

      soup = bs(browser.page_source, 'html.parser')
      soup = soup.find_all(class_='article-board article_profile')[0]  # 네이버 카페 구조 확인후 게시글 내용만 가저오기
      datas = soup.select("table > tbody > tr")

      for data in datas:
        article = data.find(class_="article")
        article_link = article.get('href')

        if article is None: continue

        article_title = article.get_text().strip()

        if article_title.__contains__("했어요]"):
          title_list = article_title.split("] ")
          article_title = title_list[-1].replace(" 반응정리", "")

          #파일로 저장
          with open('../datas/crawl.csv', 'a+', newline='', encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow([article_title, article_link])


  def select_audio(self):
    root = tk.Tk()
    root.title("오디오 선택창")
    root.geometry("400x300")

    tk.Label(root, text="Download Audio").grid(row=0, column=0, columnspan=2, padx=5, pady=5)

    listbox = tk.Listbox(root, width=50)
    listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

    with open('../datas/crawl.csv', 'r', encoding="utf-8") as f:
      rdr = csv.reader(f)
      next(rdr)  # 제목 행 skip
      lines = list(rdr)

    for line in lines: listbox.insert(tk.END, f"{line[0]}")

    def on_double_click(event):
      select = listbox.curselection()
      if select:
        self.url = lines[select[0]][1]
        root.destroy()

    listbox.bind("<Double-1>", on_double_click)
    root.mainloop()


  def download_audio(self):

    youtube_links = []
    download_path = "../datas/video"
    
    self.select_audio()

    if self.url is None:
      return

    #진행바 설정
    root = tk.Tk()
    root.title("다운로드 진행바")
    root.geometry("400x80")

    bar = ttk.Progressbar(root, length=360, mode='determinate')
    bar.pack(pady=20)
    bar["maximum"] = 300
    bar["value"] = 0
    root.update()

    #기존 파일 삭제
    clear_folder('../datas/video')
    clear_folder('../datas/audio')

    browser = login(self.id, self.pw)
    browser.get("https://cafe.naver.com" + self.url)

    time.sleep(2)

    browser.switch_to.frame('cafe_main')
    soup = bs(browser.page_source, 'html.parser')
    datas = soup.find_all(class_='se-component se-oembed se-l-default __se-component')

    #유튜브 링크 가져오기
    for data in datas:
      data = data.find_all_next(class_='__se_module_data')[0]
      watch_url = change_to_youtube_url(data)
      youtube_links.append(watch_url)

    browser.quit()

    #진행바 길이 설정
    total_links = len(youtube_links) * 2
    bar["maximum"] = total_links
    root.update()

    #유튜브 영상 다운로드
    for link in youtube_links:
      yt = YouTube(link)
      title = get_viewer(yt.author, yt.title)

      stream = yt.streams.get_highest_resolution()
      stream.download(output_path=download_path,filename=title+".mp4")
      mp4_path = download_path+"/"+title+".mp4"
      audio_clip = AudioFileClip(mp4_path)
      audio_clip.write_audiofile("audio/"+title+".wav",verbose=False, logger=None)

      #프로그래스 바 업데이트
      bar["value"] += 1
      root.update()

    #오디오 시작 시간 조정
    origin, sr = librosa.load("../datas/audio/원본.wav", sr=None)

    for filename in os.listdir('../datas/audio'):
      if filename != "원본.wav":
        y, _ = librosa.load("./audio/"+filename,sr=sr)
        start_index = find_time(origin, y) * 512
        if start_index == 0:
          y = np.pad(y, (np.argmax(np.abs(origin) > 0.02), 0), 'constant')
          soundfile.write("./audio/"+filename, y,sr)
        else:
          soundfile.write("./audio/"+filename, y[start_index:],sr)

        # 프로그래스 바 업데이트
        bar["value"] += 1
        root.update()  # GUI 업데이트

    msgbox.showinfo("완료", "오디오들이 다운받아졌습니다")
    root.destroy()  # Tkinter 창 종료