import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import tkinter as tk


class Adjuster:

    def __init__(self, audio1, audio2):
        matplotlib.use('TkAgg')
        matplotlib.rcParams['axes.unicode_minus'] = False
        plt.rc('font', family='NanumGothic')

        self.audio1 = audio1
        self.audio2 = audio2

        self.first_index = np.argmax(np.abs(audio1) > 0.01)
        self.start_index = self.first_index - 256
        self.final_index = None
        self.limit = 1000

        '''그래프 설정'''
        # 그래프 초기화
        self.fig, self.ax = plt.subplots(figsize=(10, 6))  # 하나의 플롯 생성
        plt.subplots_adjust(bottom=0.25)

        # 첫 번째 신호 그래프
        x = np.linspace(0, self.limit, self.limit)
        self.line1, = self.ax.plot(x, audio1[self.first_index:self.first_index + self.limit], lw=2, label='원본')
        self.line2, = self.ax.plot(x, audio2[self.start_index:self.start_index + self.limit], lw=2, label='반응 영상')
        self.ax.set_ylim(-1, 1)
        self.ax.set_title("파장 맞추기")
        self.ax.legend()  # 범례 추가


        '''슬라이더 및 버튼 설정'''
        # 슬라이더 설정
        ax_freq = plt.axes([0.2, 0.1, 0.65, 0.03])  # 슬라이더 위치 (x, y, width, height)
        self.slider = Slider(ax_freq, '시작 인덱스', self.start_index, self.start_index + 512, valinit=self.start_index, valstep=1)

        # 버튼 설정
        ax_reset = plt.axes([0.4, 0.15, 0.2, 0.04])  # 버튼 위치 (x, y, width, height)
        self.reset_button = Button(ax_reset, '완료 시 클릭', color='lime', hovercolor='lime')

        # 슬라이더와 버튼에 함수 연결
        self.slider.on_changed(self.update)
        self.reset_button.on_clicked(self.send)


        '''화면 위치 조정'''
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


    '''슬라이더 및 버튼 작동'''
    # 슬라이더 업데이트 함수
    def update(self, val):
        idx = int(self.slider.val)  # 슬라이더 값 정수로 변환
        # 현재 인덱스에 해당하는 y 값 가져오기
        current_audio = self.audio2[idx:idx + self.limit]
        # 그래프를 업데이트 (특정 인덱스에 해당하는 포인트 강조)
        self.line2.set_ydata(current_audio)  # 전체 신호를 다시 그립니다.
        self.fig.canvas.draw_idle()

    # 버튼 클릭 시 호출되는 함수
    def send(self, event):
        self.final_index = int(self.slider.val) - self.first_index
        plt.close()


    # 그래프 표시
    def show(self):
        plt.show()