import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import tkinter as tk
import librosa
import os
import sys
import soundfile

from matplotlib.widgets import Slider, Button
from tkinter import ttk, filedialog


class Adjuster:
    def __init__(self, audio1, audio2):
        matplotlib.use("TkAgg")
        matplotlib.rcParams["axes.unicode_minus"] = False
        plt.rc("font", family="NanumGothic")

        self.audio1 = audio1
        self.audio2 = audio2

        self.first_index = np.argmax(np.abs(self.audio1) > 0.02)
        self.final_index = None
        self.limit = 512
        self.slider_limit = 512

        # 그래프 초기화
        self.fig, self.ax = plt.subplots(figsize=(10, 6))  # 하나의 플롯 생성
        plt.subplots_adjust(bottom=0.25)

        # 첫 번째 신호 그래프
        self.x = np.linspace(0, self.limit, self.limit)
        (self.line1,) = self.ax.plot(
            self.x,
            self.audio1[self.first_index : self.first_index + self.limit],
            lw=2,
            label="원본",
        )
        (self.line2,) = self.ax.plot(
            self.x,
            self.audio2[self.first_index : self.first_index + self.limit],
            lw=2,
            label="반응 영상",
        )

        self.ax.set_ylim(-1, 1)
        self.ax.set_title("파장 맞추기")
        self.ax.legend()  # 범례 추가

        # 슬라이더 설정
        ax_freq = plt.axes(
            [0.15, 0.1, 0.3, 0.04]
        )  # 슬라이더 위치 (x, y, width, height)
        self.slider1 = Slider(
            ax_freq,
            "시작 인덱스",
            -self.slider_limit // 2,
            self.slider_limit // 2,
            valinit=0,
            valstep=1,
        )

        ax_freq = plt.axes([0.6, 0.1, 0.3, 0.04])  # 슬라이더 위치 (x, y, width, height)
        self.slider2 = Slider(
            ax_freq, "오디오 길이", 100, 1000, valinit=self.limit, valstep=1
        )

        # 버튼 설정
        ax_reset = plt.axes([0.4, 0.15, 0.2, 0.06])  # 버튼 위치 (x, y, width, height)
        self.reset_button = Button(
            ax_reset, "완료 시 클릭", color="lime", hovercolor="lime"
        )

        # 슬라이더와 버튼에 함수 연결
        self.slider1.on_changed(self.update_index)
        self.slider2.on_changed(self.update_length)
        self.reset_button.on_clicked(self.send)

        manager = plt.get_current_fig_manager()

        # tkinter로 화면 크기 가져오기
        root = tk.Tk()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()

        # 중앙 위치 계산
        x = (width // 2) - (self.fig.get_figwidth() * self.fig.dpi // 2)
        y = (height // 2) - (self.fig.get_figheight() * self.fig.dpi // 2)

        manager.window.wm_geometry("+%d+%d" % (x, y))

        plt.show()

    # 슬라이더 업데이트 함수
    def update_index(self, val):
        idx = int(self.slider1.val)  # 슬라이더 값 정수로 변환

        current_audio = self.audio2[
            self.first_index + idx : self.first_index + idx + self.limit
        ]

        self.line2.set_ydata(current_audio)
        self.fig.canvas.draw_idle()

    def update_length(self, val):
        idx = int(self.slider1.val)
        self.limit = int(self.slider2.val)  # 슬라이더 값 정수로 변환

        self.x = np.linspace(0, self.limit, self.limit)
        self.line1.set_xdata(self.x)
        self.line2.set_xdata(self.x)
        current_audio = self.audio2[
            self.first_index + idx : self.first_index + idx + self.limit
        ]

        self.line1.set_ydata(
            self.audio1[self.first_index : self.first_index + self.limit]
        )
        self.line2.set_ydata(current_audio)  # 전체 신호를 다시 그립니다.
        self.ax.relim()  # 데이터 범위 재계산
        self.ax.autoscale_view()  # 자동 스케일 조정
        self.fig.canvas.draw_idle()

    # 버튼 클릭 시 호출되는 함수
    def send(self, event):

        self.final_index = int(self.slider1.val)
        plt.close()


def find_absolute_time(name):
    """
    오디오 시작 시간을 찾고 조정하는 함수
    주어진 오디오 파일을 분석하여 시작 인덱스를 찾고,
    그에 따라 오디오를 조정하여 저장합니다.
    """
    sr = 44100  # 샘플링 레이트 설정
    audio1, _ = librosa.load("data/audio/원본.wav", sr=sr)  # 원본 오디오 로드
    audio2, _ = librosa.load("data/audio/" + name, sr=sr)  # 비교할 오디오 로드

    # Adjuster 클래스 인스턴스 생성
    visualizer = Adjuster(audio1, audio2)
    start_index = visualizer.final_index  # 시작 인덱스 얻기

    if start_index is None:
        return  # 시작 인덱스가 없으면 종료

    # 오디오 조정
    if start_index >= 0:
        audio2 = audio2[start_index:]  # 시작 인덱스 이후의 오디오
    else:
        audio2 = np.pad(audio2, (abs(start_index), 0), "constant")  # 패딩 추가

    folder_name = "output/adjusted"

    # 조정된 오디오 저장
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)  # 조정된 폴더 생성

    soundfile.write(folder_name + "/" + name, audio2, sr)  # 파일 저장

    option = OptionWindow()
    option.read_audio()  # 오디오 파일 선택

    if option.sel is None:
        return  # 선택된 파일이 없으면 종료

    find_absolute_time(option.sel)  # 선택된 파일에 대해 다시 시작 시간 찾기
