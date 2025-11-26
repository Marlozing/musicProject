import asyncio
import os
import subprocess
import sqlite3
import time
import warnings
import json
import threading
import numpy as np
import soundfile as sf
import requests
import zipfile

from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup as bs
# from pytubefix import YouTube  <-- Pytube 제거
import yt_dlp  # yt-dlp 라이브러리 추가
from dotenv import load_dotenv

# region 기존 함수들은 그대로 유지 (편의상 생략)
# ... (change_to_youtube_url, get_viewer, process_title, get_html, format_time 함수는 동일)
# ... (FindStartTime 모듈은 현재 파일에 없으므로 주석 처리된 부분 유지)
# endregion

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
        "징버거가 짱이다": "[징버거]",
        "릴파의 순간들": "[릴파]",
        "봉인 풀린 주르르": "[주르르]",
        "고세구의 좀더": "[고세구]",
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

        # yotubes_dict는 이제 URL을 저장합니다.
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
        # yt-dlp가 오디오 변환을 처리하므로 이 함수는 merge_audio에서만 사용됩니다.
        try:
            conv_result = await asyncio.to_thread(
                subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
            # check=True로 설정하여 returncode != 0 검사는 subprocess가 처리하도록 함.
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode(errors="replace")
            await self.write_progress(f"FFMPEG error for {command}: {err_msg}")
            return
        except Exception as e:
            await self.write_progress(f"FFMPEG exception for {command}: {e}")
            return

    # endregion

    # region 유튜브 다운로드 (yt-dlp 사용)
    async def download_youtube(self, title: str, output_path: str = None):
        if output_path is None:
            output_path = self.raw_dir

        url_to_download = self.youtubes_dict.get(title)

        if url_to_download is None:
            await self.write_progress(f"Error: URL not found for {title}")
            return

        await self.write_progress(f"Downloading {title}...")

        # 1. 비디오 + 오디오 (MP4 컨테이너) 다운로드
        # yt-dlp가 최적의 비디오/오디오 스트림을 다운로드하고 MP4로 병합합니다.
        video_output_template = os.path.join(output_path, f"{title}.%(ext)s")

        video_command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",  # 최적의 mp4 포맷 선택
            url_to_download,
            "-o", video_output_template,
            "--merge-output-format", "mp4",
            "-S", "res:1080",  # 1080p 해상도 우선
            "--no-warnings"
        ]

        # 2. 오디오 스트림 추출 및 WAV 파일로 변환
        # yt-dlp의 포스트프로세서를 사용하여 WAV 변환을 자동으로 수행합니다.
        audio_wav_path = os.path.join(output_path, f"{title}.wav")

        audio_command = [
            "yt-dlp",
            "-f", "bestaudio[ext=webm][acodec=opus]/bestaudio/best",  # 최고의 오디오 스트림 선택 (Opus 또는 AAC)
            url_to_download,
            "-o", audio_wav_path,
            "--extract-audio",  # 오디오 추출 활성화
            "--audio-format", "wav",  # WAV 포맷으로 출력
            "--audio-quality", "0",  # 최고 품질 (무손실 WAV)
            "--postprocessor-args", "AudioConvertor:-ac 2 -ar 44100",  # 채널 2, 샘플레이트 44.1kHz 지정
            "--no-warnings"
        ]

        try:
            # yt-dlp 명령어를 비동기로 실행
            video_task = asyncio.to_thread(subprocess.run, video_command, check=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
            audio_task = asyncio.to_thread(subprocess.run, audio_command, check=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)

            # 두 작업을 동시에 실행
            await asyncio.gather(video_task, audio_task)

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode(errors="replace")
            await self.write_progress(f"YT-DLP process error for {title}: {err_msg}")
            return
        except Exception as e:
            await self.write_progress(f"Download/Process error for {title}: {e}")
            return

        await self.write_progress(f"Downloaded and Converted {title}")

    # endregion

    # region 동영상 파일 시간 조정
    async def adjust_audio_start_time(self, title: str):
        # yt-dlp로 WAV 파일이 생성되었으므로, WAV 파일을 바로 사용
        audio, sr = await asyncio.to_thread(
            sf.read, f"{self.raw_dir}/{title}.wav", dtype='float32'
        )

        start_index = 0  # await find_time(self.origin_audio, audio[0]) * 512
        start_time = start_index / sr

        await asyncio.to_thread(
            sf.write,
            f"{self.compiled_dir}/{title}.wav",
            audio[:, start_index:] if audio.ndim > 1 else audio[start_index:],
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

    # region 오디오 병합 (기존 로직 유지)
    async def merge_audio(self, title: str):
        # yt-dlp로 다운로드한 mp4와 ffmpeg로 추출된 wav 파일을 병합합니다.
        ffmpeg_merge_command = [
            "ffmpeg",
            "-y",  # 덮어쓰기 옵션
            "-i",
            f"{self.compiled_dir}/{title}.mp4",  # 비디오 파일
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

    # region ZIP 파일 생성 (기존 로직 유지)
    async def create_zip(self, output_path: str, zip_name: str):
        zip_path = os.path.join(output_path, zip_name)
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for entry in os.listdir(self.temp_dir):
                entry_path = os.path.join(self.temp_dir, entry)
                if os.path.isfile(entry_path) and entry_path.endswith(".mkv"):
                    zipf.write(entry_path, arcname=entry)

        return zip_path

    # endregion

    # region 최종 다운로드 함수 (yt-dlp 정보 추출 사용)
    async def download_audio(self, url_id: str):
        print("Downloading audio...")
        # 유튜브 링크 가져오기
        youtube_links = await get_html(url_id)

        # region 에러 처리
        if len(youtube_links) == 0:
            raise Exception("No link found")
        # endregion

        # region 유튜브 영상 정보 추출 및 링크 저장
        for link in youtube_links:
            try:
                # NEW: yt-dlp로 정보 추출 (Pytube 대체)
                ydl_opts = {'quiet': True, 'noprogress': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, link, download=False)

                author = info.get('uploader', 'Unknown Author')
                title = info.get('title', 'Unknown Title')

                self.youtubes_dict[get_viewer(author, title)] = link  # URL 저장

            except Exception as e:
                print(f"Error: {link} : {e}")
                pass
        # endregion

        if len(self.youtubes_dict) <= 1:  # 원본 포함이므로 <= 1이면 영상이 부족함
            raise Exception("No video found (or only one video)")

        default_name = "원본"

        if not "원본" in self.youtubes_dict.keys():
            await self.write_progress("No original video")
            await self.write_progress(
                f"Use {list(self.youtubes_dict.keys())[0]} as default"
            )
            default_name = list(self.youtubes_dict.keys())[0]

        # region 원본 영상 처리
        await self.download_youtube(default_name, output_path="./video")  # is_original 플래그 제거
        '''
        await self.merge_audio(default_name)
        del self.youtubes_dict[default_name]
        # endregion

        # 원본 오디오 로드 (yt-dlp가 생성한 WAV 파일을 로드)
        audio_data, sr = await asyncio.to_thread(
            sf.read, f"./video/원본.wav", dtype='float32'
        )

        self.origin_audio = audio_data
        '''
        # region 다운로드 및 시간 조정
        for key in self.youtubes_dict.keys():
            await self.download_youtube(key, output_path="./video")

        print(f"All video downloaded for {url_id}")

        raise Exception("Test Exception - Remove this line after testing")
        for key in self.youtubes_dict.keys():
            await self.adjust_audio_start_time(key)
            await self.merge_audio(key)

        await self.create_zip(output_path=self.download_path, zip_name=f"{url_id}.zip")
        # endregion

    # endregion