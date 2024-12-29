import asyncio
import os
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
import sqlite3
import time
import warnings

import librosa
import numpy as np
import soundfile
from bs4 import BeautifulSoup as bs
from pytubefix import YouTube
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from .FindStartTime import find_time

# region 특정 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
warnings.filterwarnings(
    "ignore", category=FutureWarning, message="librosa.core.audio.__audioread_load.*"
)
# endregion


# region 폴더 정리
def clear_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path)  # 폴더가 없으면 생성
    else:
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)  # 파일 삭제


# endregion


# region 로그인
def login(naver_id: str, naver_pw: str):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Headless 모드
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Remote(
        command_executor="http://localhost:4444/wd/hub", options=options
    )

    login_url = "https://nid.naver.com/nidlogin.login"

    driver.get(login_url)  # 로그인 페이지 열기
    driver.implicitly_wait(2)  # 로드 대기

    driver.execute_script(
        f"document.getElementsByName('id')[0].value='{naver_id}'"
    )  # ID 입력
    driver.execute_script(
        f"document.getElementsByName('pw')[0].value='{naver_pw}'"
    )  # 비밀번호 입력
    driver.find_element(
        by=By.XPATH, value='//*[@id="log.login"]'
    ).click()  # 로그인 버튼 클릭
    time.sleep(1)  # 잠시 대기

    return driver


# endregion


# region 유튜브 URL 변환
def change_to_youtube_url(source: str) -> str:
    video_id = (
        source.split("src=")[1]
        .split('"')[1]
        .replace("\\", "")
        .split("/")[-1]
        .split("?")[0]
    )  # 비디오 ID 추출
    return f"https://www.youtube.com/watch?v={video_id}"  # 유튜브 URL 반환


# endregion


# region 동영상 파일 이름 결정
def get_viewer(author: str, title: str) -> str:
    names = [
        "우왁굳",
        "아이네",
        "징버거",
        "릴파",
        "주르르",
        "고세구",
        "비챤",
        "뢴트게늄",
    ]
    authors = {
        "우왁굳의 반찬가게": "[우왁굳]",
        "데친 숙주나물": "[아이네]",
        "징버거가 ZZANG센 주제에 너무 신중하다": "[징버거]",
        "릴파의 순간들": "[릴파]",
        "주르르": "[주르르]",
        "고세구의 짧은거": "[고세구]",
        "비챤의 나랑놀아": "[비챤]",
        "하치키타치": "[뢴트게늄]",
    }
    wav_path = "원본"  # 기본 경로

    if author == "반응정리":
        for name in names:
            if name in title.split(" ")[0]:  # 제목의 첫 단어와 비교
                wav_path = title.split(" ")[0]  # 첫 단어를 경로로 설정

    if author in authors:
        wav_path = authors[author]

    return wav_path  # 최종 이름 반환


# endregion 로그인 함수


# region 제목 처리
def process_title(title: str):
    if "했어요]" in title:
        splited_title = title.split("했어요]")[1].replace(" 반응정리", "").split("/")
    else:
        splited_title = title.replace(" 반응정리", "").split("/")

    final_title = "".join(splited_title[:-1])
    viewer = splited_title[-1]

    viewer = viewer.replace("💙", "🩵")
    viewer = viewer.replace("🖤", "💙")

    return [final_title, viewer]


# endregion


class DownloadAudio:
    # region 초기화
    def __init__(self, data: dict):
        self.url = data["link"]
        self.reactions = data["reactions"]
        db_conn = sqlite3.connect("./database/posted_link.db")
        db_cur = db_conn.cursor()
        db_cur.execute("SELECT * FROM posted_link ORDER BY link DESC")
        self.db_list = db_cur.fetchall()
        db_conn.close()
        self.temp_dir = TemporaryDirectory().name
        self.origin_audio = None

    # endregion

    # region 유튜브 다운로드
    async def download_youtube(self, yt: YouTube, title: str):
        video_stream = yt.streams.filter(
            resolution="1080p", file_extension="mp4"
        ).first()
        audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").first()

        try:
            video_stream.download(output_path=self.temp_dir, filename=f"{title}.mp4")
            audio_stream.download(output_path=self.temp_dir, filename=f"{title}.wav")
        except:
            print(f"Error: {title}")
            return

    # endregion

    # region 동영상 파일 시간 조정
    async def adjust_audio_start_time(self, title: str, output_path: str = "../video"):
        audio, _ = await asyncio.to_thread(
            librosa.load, f"{self.temp_dir}/{title}.wav", sr=None
        )
        start_index = await find_time(self.origin_audio, audio) * 512
        start_time = start_index / 44100

        await asyncio.to_thread(
            soundfile.write,
            f"{self.temp_dir}/{title}.wav",
            audio[start_index:],
            44100,
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"00:00:{start_time}",  # 시작 시간
            "-i",
            f"{self.temp_dir}/{title}.mp4",  # 입력 비디오 파일
            "-c",
            "copy",  # 비디오와 오디오를 재인코딩하지 않고 복사
            f"{self.temp_dir}/{title}_compiled.mp4",  # 출력 비디오 파일
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        command = [
            "ffmpeg",
            "-i",
            f"{self.temp_dir}/{title}_compiled.mp4",
            "-i",
            f"{self.temp_dir}/{title}.wav",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-strict",
            "experimental",
            f"{output_path}/{title}.mp4",
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    # endregion

    # region 오디오 다운로드 함수
    async def download_audio(self, naver_id: str, naver_pw: str):
        youtube_links = []
        download_tasks = []
        adjust_tasks = []
        download_path = "../video"

        # region 기존 파일 삭제
        clear_folder(download_path)
        # endregion

        # region 크롤링
        browser = login(naver_id, naver_pw)

        browser.get(self.url)

        time.sleep(2)

        browser.switch_to.frame("cafe_main")
        soup = bs(browser.page_source, "html.parser")
        title = soup.find_all(class_="title_text")[0].text
        if process_title(title)[1] != self.reactions:
            db_conn = sqlite3.connect("./database/posted_link.db")
            db_conn.execute(
                "UPDATE posted_link SET title = ? WHERE link = ?",
                (title, self.url),
            )
            db_conn.commit()

        datas = soup.find_all(
            class_="se-component se-oembed se-l-default __se-component"
        )
        # endregion

        # region 유튜브 링크 가져오기
        for data in datas:
            data = data.find_all_next(class_="__se_module_data")[0]
            watch_url = change_to_youtube_url(str(data))
            youtube_links.append(watch_url)
        browser.quit()
        # endregion

        # region 에러 처리
        if len(youtube_links) == 0:
            print("ERROR")
            return
        # endregion

        # region 유튜브 영상 다운로드
        youtubes_dict = {}
        for link in youtube_links:
            try:
                yt = YouTube(link)
                youtubes_dict[get_viewer(yt.author, yt.title)] = yt
            except:
                pass

        default_video_name = "원본"
        if not "원본" in youtubes_dict.keys():
            default_video_name = list(youtubes_dict.keys())[0]

        # region 원본 영상 처리
        await self.download_youtube(youtubes_dict[default_video_name], "원본")
        del youtubes_dict[default_video_name]

        command = [
            "ffmpeg",
            "-i",
            f"{self.temp_dir}/원본.mp4",
            "-i",
            f"{self.temp_dir}/원본.wav",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-strict",
            "experimental",
            f"{download_path}/원본.mp4",
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # endregion

        if len(youtubes_dict) == 0:
            return

        self.origin_audio, _ = librosa.load(
            f"{self.temp_dir}/원본.wav", sr=None, mono=True
        )

        # region 다운로드 및 시간 조정
        for key in youtubes_dict.keys():
            download_tasks.append(self.download_youtube(youtubes_dict[key], key))
            adjust_tasks.append(self.adjust_audio_start_time(key, download_path))

        await asyncio.gather(*download_tasks)
        await asyncio.gather(*adjust_tasks)
        # endregion

        # endregion

    # endregion
