import time
import csv
import librosa
import tkinter as tk
import numpy as np

from bs4 import BeautifulSoup as bs

from functions import login

class DownloadAudio:
  def __init__(self, id, pw):
    self.id = id
    self.pw = pw
    self.url = None

  def read_cafe(self, length=1):

    total_list = ["제목", "링크"]

    f = open('crawl.csv', 'w', encoding="utf-8", newline='')
    wr = csv.writer(f)
    wr.writerow([total_list[0], total_list[1]])
    f.close()

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

          '''파일로 저장'''
          f = open('crawl.csv', 'a+', newline='', encoding="utf-8")
          wr = csv.writer(f)

          wr.writerow([article_title, article_link])
          f.close()

  def select_audio(self):
    root = tk.Tk()
    root.title("오디오 선택창")
    root.geometry("400x300")

    tk.Label(root, text="Download Audio").grid(row=0, column=0, columnspan=2, padx=5, pady=5)

    listbox = tk.Listbox(root, width=50)
    listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

    with open('crawl.csv', 'r', encoding="utf-8") as f:
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

    import soundfile
    import os
    from pytubefix import YouTube
    from moviepy.editor import AudioFileClip
    from tkinter import ttk
    import tkinter.messagebox as msgbox

    from functions import clear_folder, change_to_youtube_url, get_viewer
    from findStartTime import find_time

    youtube_links = []
    download_path = "video"
    
    self.select_audio()

    if self.url is None:
      return

    '''진행바 설정'''
    root = tk.Tk()
    root.title("다운로드 진행바")
    root.geometry("400x100")

    bar = ttk.Progressbar(root, length=1, mode='determinate')
    bar.pack(pady=20)
    bar["maximum"] = 1
    bar["value"] = 0
    root.update()

    '''기존 파일 삭제'''
    clear_folder('./video')
    clear_folder('./audio')

    browser = login(self.id, self.pw)
    browser.get("https://cafe.naver.com" + self.url)

    time.sleep(2)

    browser.switch_to.frame('cafe_main')
    soup = bs(browser.page_source, 'html.parser')
    datas = soup.find_all(class_='se-component se-oembed se-l-default __se-component')

    '''유튜브 링크 가져오기'''
    for data in datas:
      data = data.find_all_next(class_='__se_module_data')[0]
      youtube_link = str(data).split("src=")[1].split('"')[1].replace("\\","")
      watch_url = change_to_youtube_url(youtube_link)
      youtube_links.append(watch_url)

    browser.quit()  # 브라우저 종료

    '''진행바 길이 설정'''
    total_links = len(youtube_links) * 2
    bar["maximum"] = total_links

    '''유튜브 영상 다운로드'''
    for link in youtube_links:
      yt = YouTube(link)
      title = get_viewer(yt.author, yt.title)

      stream = yt.streams.get_highest_resolution()
      stream.download(output_path=download_path,filename=title+".mp4")
      mp4_path = download_path+"/"+title+".mp4"
      audio_clip = AudioFileClip(mp4_path)
      audio_clip.write_audiofile("audio/"+title+".wav",verbose=False, logger=None)

      '''프로그래스 바 업데이트'''
      bar["value"] += 1
      root.update()

    '''오디오 시작 시간 조정'''
    origin, sr = librosa.load("./audio/원본.wav", sr=None)

    for filename in os.listdir('./audio'):
      if filename != "원본.wav":
        y, _ = librosa.load("./audio/"+filename,sr=sr)
        start_index = find_time(origin, y) * 512
        print(start_index, filename)
        if start_index == 0:
          print(filename, np.argmax(np.abs(origin) > 0.02))
          y = np.pad(y, (np.argmax(np.abs(origin) > 0.02), 0), 'constant')
          soundfile.write("./audio/"+filename, y,sr)
        else:
          soundfile.write("./audio/"+filename, y[start_index:],sr)

        # 프로그래스 바 업데이트
        bar["value"] += 1
        root.update()  # GUI 업데이트

    msgbox.showinfo("완료", "오디오들이 다운받아졌습니다")
    root.destroy()  # Tkinter 창 종료