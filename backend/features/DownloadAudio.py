import asyncio
import os
import subprocess
import sqlite3
import time
import warnings
import json
import threading
import librosa
import numpy as np
import soundfile
import requests
import zipfile

from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup as bs
from pytubefix import YouTube
from dotenv import load_dotenv

from .FindStartTime import find_time

# region 특정 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
warnings.filterwarnings(
    "ignore", category=FutureWarning, message="librosa.core.audio.__audioread_load.*"
)
# endregion


# region 유튜브 URL 변환
def change_to_youtube_url(embed_url: str) -> str:
    # URL에서 비디오 ID 추출
    video_id = embed_url.split("/")[-1].split("?")[0]
    # 일반 링크 형식으로 변환
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    return watch_url


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
                break

    if author in authors and "반응" in title:
        wav_path = authors[author]

    return wav_path  # 최종 이름 반환


# endregion 로그인 함수


# region 제목 처리
def process_title(title: str) -> list:

    if "했어요]" in title:
        splited_title = title.split("했어요]")[1].replace(" 반응정리", "").split("/")
    else:
        splited_title = title.replace(" 반응정리", "").split("/")

    final_title = "".join(splited_title[:-1])
    viewer = splited_title[-1]

    # 이모지 처리
    viewer = viewer.replace("💙", "🩵")
    viewer = viewer.replace("🖤", "💙")

    return [final_title, viewer]


# endregion


# region HTML 가져오기
async def get_html(article_id: str):
    url = f"{os.getenv('NAVER_CAFE_HTML_API')}/{os.getenv('NAVER_CAFE_ID')}/articles/{article_id}?useCafeId=false"
    response = requests.get(url)
    data = response.json()
    # HTML 파싱
    soup = bs(data["result"]["article"]["contentHtml"], "html.parser")

    # '__se_module_data' 클래스를 가진 모든 스크립트 태그 찾기
    datas = soup.find_all(class_="__se_module_data")

    youtube_links = []
    for data in datas:
        # data-module 속성에서 JSON 데이터 추출
        module_data = data.get("data-module")
        if module_data:
            a = json.loads(module_data)["data"]
            if a.get("html") is None:
                continue

            # HTML 내용에서 <iframe> 태그 추출
            iframe_html = a["html"]
            iframe_soup = bs(iframe_html, "html.parser")
            iframe = iframe_soup.find("iframe")

            # src 속성 추출
            if iframe and "src" in iframe.attrs:
                youtube_links.append(change_to_youtube_url(iframe["src"]))
    return youtube_links


# endregion


# region 시간 포맷팅
def format_time(seconds: float) -> str:
    """초 단위의 시간을 HH:MM:SS.ms 형태로 변환합니다."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"


# endregion


class DownloadAudio:
    # region 초기 설정
    def __init__(self, progress_list: list):
        load_dotenv("crawl.env")

        # 임시 폴더 생성
        with TemporaryDirectory() as temp_dir:
            self.temp_dir = temp_dir
            self.raw_dir = os.path.join(self.temp_dir, "raw")
            self.compiled_dir = os.path.join(self.temp_dir, "compiled")

            os.mkdir(self.raw_dir)
            os.mkdir(os.path.join(self.raw_dir, "audio"))
            os.mkdir(self.compiled_dir)

        self.youtubes_dict = {}
        self.origin_audio = None
        self.download_path = "./video"
        self.music_title = "음악"
        self.progress_list = progress_list

    # endregion

    # region 진행 상황 출력
    async def write_progress(self, message: str):
        self.progress_list.append(message)
        print(message)

    # endregion

    # region ffmpeg 변환
    async def ffmpeg_convert_file(self, command: list):
        try:
            conv_result = await asyncio.to_thread(
                subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if conv_result.returncode != 0:
                err_msg = conv_result.stderr.decode(errors="replace")
                await self.write_progress(f"FFMPEG error for {command}: {err_msg}")
                return
        except Exception as e:
            await self.write_progress(f"FFMPEG exception for {command}: {e}")
            return

    # endregion

    # region 유튜브 다운로드
    async def download_youtube(self, title: str, output_path: str = None):
        if output_path is None:
            output_path = self.raw_dir

        yt = self.youtubes_dict.get(title)
        video_stream = yt.streams.filter(
            resolution="1080p", file_extension="mp4"
        ).first()
        audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").first()

        if video_stream is None or audio_stream is None:
            await self.write_progress(
                f"Error: '{title}'에 대해 적절한 스트림을 찾지 못했습니다."
            )
            return

        print(f"Downloading {title}...")

        try:
            # 비디오와 오디오 다운로드를 동시에 실행 (blocking 함수를 별도 스레드로 실행)
            download_tasks = [
                asyncio.to_thread(
                    video_stream.download,
                    output_path=output_path,
                    filename=f"{title}.mp4",
                ),
                asyncio.to_thread(
                    audio_stream.download,
                    output_path=os.path.join(output_path, "audio"),
                    filename=f"{title}.mp4",
                ),
            ]
            await asyncio.gather(*download_tasks)
        except Exception as e:
            await self.write_progress(f"Download error for {title}: {e}")
            return

        ffmpeg_conv_command = [
            "ffmpeg",
            "-y",  # 덮어쓰기 옵션
            "-i",
            f"{output_path}/audio/{title}.mp4",  # 원본 오디오 파일 (mp4 컨테이너 내 오디오 스트림)
            "-ar",
            "44100",  # 샘플레이트 조정 (필요 시 변경)
            f"{output_path}/{title}.wav",  # 출력 WAV 파일
        ]

        await self.ffmpeg_convert_file(ffmpeg_conv_command)
        await self.write_progress(f"Downloaded {title}")

    # endregion

    # region 동영상 파일 시간 조정
    async def adjust_audio_start_time(self, title: str):
        audio, sr = await asyncio.to_thread(
            librosa.load, f"{self.raw_dir}/{title}.wav", sr=None, mono=False
        )

        start_index = await find_time(self.origin_audio, audio[0]) * 512
        start_time = start_index / sr

        await asyncio.to_thread(
            soundfile.write,
            f"{self.compiled_dir}/{title}.wav",
            audio[:, start_index:].T,
            sr,
        )

        formateed_time = format_time(start_time)
        ffmpeg_merge_command = [
            "ffmpeg",
            "-y",
            "-ss",
            formateed_time,  # 시작 시간
            "-i",
            f"{self.raw_dir}/{title}.mp4",  # 입력 비디오 파일
            "-c",
            "copy",  # 비디오와 오디오를 재인코딩하지 않고 복사
            f"{self.compiled_dir}/{title}.mp4",  # 출력 비디오 파일
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            ffmpeg_merge_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            err_msg = result.stderr.decode(errors="replace")
            await self.write_progress(f"Error adjusting {title}: {err_msg}")
        else:
            await self.write_progress(f"Adjusted {title}")

    # endregion

    # region 오디오 병합
    async def merge_audio(self, title: str):
        ffmpeg_merge_command = [
            "ffmpeg",
            "-y",  # 덮어쓰기 옵션일
            "-i",
            f"{self.compiled_dir}/{title}.mp4",  # 비디오 파
            "-i",
            f"{self.compiled_dir}/{title}.wav",  # WAV 오디오 파일
            "-c:v",
            "copy",  # 비디오 스트림은 재인코딩 없이 그대로 복사
            "-map",
            "0:v:0",  # 첫 번째 입력의 비디오 스트림 선택
            "-map",
            "1:a:0",  # 두 번째 입력의 오디오 스트림 선택
            f"{self.temp_dir}/{title}.mkv",
        ]

        await self.ffmpeg_convert_file(ffmpeg_merge_command)
        await self.write_progress(f"Merged {title}")

    # endregion

    # region ZIP 파일 생성
    async def create_zip(self, output_path: str, zip_name: str):
        zip_path = os.path.join(output_path, zip_name)
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for entry in os.listdir(self.temp_dir):
                entry_path = os.path.join(self.temp_dir, entry)
                if os.path.isfile(entry_path) and entry_path.endswith(".mkv"):
                    zipf.write(entry_path, arcname=entry)

        return zip_path

    # endregion

    # region 최종 다운로드 함수
    async def download_audio(self, url_id: str):

        print("Downloading audio...")
        # 유튜브 링크 가져오기
        youtube_links = await get_html(url_id)

        # region 에러 처리
        if len(youtube_links) == 0:
            raise Exception("No link found")
        # endregion

        # region 유튜브 영상 다운로드
        for link in youtube_links:
            try:
                yt = YouTube(link)
                self.youtubes_dict[get_viewer(yt.author, yt.title)] = yt

            except Exception as e:
                print(f"Error: {link} : {e}")
                pass
        # endregion

        if len(self.youtubes_dict) == 1:
            raise Exception("No video found")

        default_name = "원본"

        if not "원본" in self.youtubes_dict.keys():
            await self.print_progress("No original video")
            await self.print_progress(
                f"Use {list(self.youtubes_dict.keys())[0]} as default"
            )
            default_name = list(self.youtubes_dict.keys())[0]

        # region 원본 영상 처리
        await self.download_youtube(default_name, output_path=self.compiled_dir)
        await self.merge_audio(default_name)
        del self.youtubes_dict[default_name]
        # endregion

        # 원본 오디오 로드
        self.origin_audio, _ = librosa.load(
            f"{self.compiled_dir}/원본.wav", sr=None, mono=True
        )

        # region 다운로드 및 시간 조정
        for key in self.youtubes_dict.keys():
            await self.download_youtube(key)

        print(f"All video downloaded for {url_id}")

        for key in self.youtubes_dict.keys():
            await self.adjust_audio_start_time(key)
            await self.merge_audio(key)

        await self.create_zip(output_path=self.download_path, zip_name=f"{url_id}.zip")
        # endregion

    # endregion
