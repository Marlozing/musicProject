def login(id, pw):

  import time

  from selenium import webdriver
  from selenium.webdriver.common.by import By


  # 네이버 로그인 url
  url = 'https://nid.naver.com/nidlogin.login'

  options = webdriver.ChromeOptions()
  #options.add_argument('headless')
  options.add_argument('window-size=1920x1080')
  options.add_argument("disable-gpu")

  browser = webdriver.Chrome(options=options)

  browser.get(url)
  browser.implicitly_wait(2)

  # 로그인
  browser.execute_script("document.getElementsByName('id')[0].value=\'" + id + "\'")
  browser.execute_script("document.getElementsByName('pw')[0].value=\'" + pw + "\'")
  browser.find_element(by=By.XPATH, value='//*[@id="log.login"]').click()
  time.sleep(1)

  return browser

def clear_folder(path):

  import os

  if not os.path.exists(path):
    os.makedirs(path)
    return
  for filename in os.listdir(path):
    file_path = os.path.join(path, filename)
    if os.path.isfile(file_path):  # 파일인지 확인
      os.remove(file_path)  # 파일 삭제

def change_to_youtube_url(oembed_link):
  # 임베디드된 주소에서 유튜브 비디오의 고유 ID 추출
  video_id = oembed_link.split("/")[-1].split("?")[0]

  # 실행 가능한 유튜브 주소로 변환
  watch_url = f"https://www.youtube.com/watch?v={video_id}"

  return watch_url

def get_viewer(author, title):
  # wav 파일로 변환하여 저장
  names = ["우왁굳","아이네","징버거","릴파","주르르","고세구","비챤","뢴트게늄"]
  authors = {
    "우왁굳의 반찬가게": "[우왁굳]",
    "데친 숙주나물": "[아이네]",
    "징버거가 ZZANG센 주제에 너무 신중하다": "[징버거]",
    "릴파의 순간들": "[릴파]",
    "주르르": "[주르르]",
    "고세구의 짧은거": "[고세구]",
    "비챤의 나랑놀아": "[비챤]",
    "하치키타치": "[뢴트게늄]"}
  wav_path = "원본"

  for i in names:
      if author == "반응정리":
        if i in title.split(" ")[0]:
          wav_path = title.split(" ")[0]
  for i in authors:
      if author == i:
          wav_path = authors[i]

  return wav_path

def find_start_time(name):
    from waveform_adjuster import Adjuster

    import librosa
    import numpy as np
    import os
    import soundfile

    sr = 44100

    audio1, _ = librosa.load("audio/원본.wav", sr=sr)
    audio2, _ = librosa.load("audio/" + name + ".wav", sr=sr)

    # AudioVisualizer 클래스 인스턴스 생성
    visualizer = Adjuster(audio1, audio2)

    # 그래프 표시
    visualizer.show()

    start_index = visualizer.final_index

    if start_index is not None:
        if start_index >= 0:
            audio2 = audio2[start_index:]
        else:
            audio2 = np.pad(audio2, (abs(start_index), 0), 'constant')
        if not os.path.exists("adjusted"):
            os.makedirs("adjusted")
        soundfile.write("adjusted/" + name + ".wav", audio2, sr)

def visualize_audio(audio_path1, audio_path2):
    import matplotlib.pyplot as plt
    import librosa
    
    audio1, _ = librosa.load(audio_path1)
    audio2, _ = librosa.load(audio_path2)
    plt.plot(audio1[:6000], label="audio1")
    plt.plot(audio2[:6000], label="audio2")
    plt.legend()
    plt.show()
if __name__ == "__main__":
    import librosa
    import numpy as np

    audio1, _ = librosa.load("audio/원본.wav")
    print(np.argmax(np.abs(audio1) > 0.02))