import tkinter as tk
import os

from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox as msgbox


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


class SelfAdjuster:
    def __init__(self):
        # Tkinter GUI 설정
        self.root = tk.Tk()
        self.root.title("User Input Form")
        self.root.geometry("400x400")  # GUI 크기 설정
        self.origin_path = (
            "data/audio/원본.wav" if os.path.exists("data/audio/원본.wav") else None
        )
        self.compare_path = None

        ttk.Label(self.root, text="Read Audio").grid(
            row=0, column=0, columnspan=2, padx=5, pady=5
        )

        self.get_origin_button = tk.Button(
            self.root, text="원본 파일 열기", command=self.get_origin
        )
        self.get_origin_button.grid(row=1, column=0, padx=5, pady=5)

        self.get_compare_button = tk.Button(
            self.root, text="반응 파일 열기", command=self.get_compare
        )
        self.get_compare_button.grid(row=1, column=1, padx=5, pady=5)

        self.submit_button = tk.Button(self.root, text="Submit", command=self.submit)
        self.submit_button.grid(row=9, column=0, columnspan=2, padx=5, pady=5)

        self.quit_button = tk.Button(self.root, text="Quit", command=self.on_closing)
        self.quit_button.grid(row=10, column=0, columnspan=2, padx=5, pady=5)

        # GUI 실행
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def get_origin(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])

        if file_path:
            self.origin_path = file_path
            self.get_origin_button["text"] = f"{file_path.split('/')[-1]} 선택됨"

    def get_compare(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])

        if file_path:
            self.compare_path = file_path
            self.get_compare_button["text"] = f"{file_path.split('/')[-1]} 선택됨"

    def submit(self):
        if not self.origin_path or not self.compare_path:
            msgbox.showerror("Error", "원본 파일과 반응 파일를 선택해주세요.")
            return

        origin, _ = librosa.load(self.origin, sr=None)
        y, sr = librosa.load(self.compare_path, sr=None)
        file_name = file_path.split("/")[-1]

        folder_name = "output/self adjusted"

        # 조정된 오디오 저장
        start_index = find_time(origin, y) * 512

        if start_index == 0:
            y = np.pad(y, (np.argmax(np.abs(origin) > 0.02), 0), "constant")

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)  # 조정된 폴더 생성

        soundfile.write(folder_name + "/" + file_name, y, sr)  # 파일 저장
        open_folder(folder_name)

    def on_closing(self):
        self.root.destroy()


if __name__ == "__main__":
    SelfAdjuster()
