import os
import tkinter as tk

from tkinter import ttk

from downloadAudio import DownloadAudio
from musicProject.functions import find_start_time


class OptionWindow:
    def __init__(self):
        self.sel = None
        
    def read_audio(self):
        root = tk.Tk()
        root.title("Option Window")
        root.geometry("400x300")
        
        tk.Label(root, text="Read Audio").grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        
        listbox = tk.Listbox(root, width=50)
        listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        for file in os.listdir("audio"):
            if file.endswith(".wav") and "원본" not in file:
                listbox.insert(tk.END, file)

        def on_double_click(event):
            select = listbox.curselection()
            if select:  # 선택된 항목이 있는지 확인
                self.sel = listbox.get(select[0])
                root.destroy()  # Tkinter 루프 종료
            
        listbox.bind("<Double-1>", on_double_click)
        root.mainloop()
class Main:
    def __init__(self):
        # Tkinter GUI 설정
        self.root = tk.Tk()
        self.root.title("User Input Form")
        self.root.geometry("400x400")  # GUI 크기 설정

        # ID 입력
        ttk.Label(self.root, text="Naver ID:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_id = ttk.Entry(self.root, justify='center')
        self.entry_id.grid(row=0, column=1, padx=5, pady=5)

        # 비밀번호 입력
        ttk.Label(self.root, text="Password:").grid(row=1, column=0, padx=5, pady=5)
        self.entry_pw = ttk.Entry(self.root, show="*", justify='center')
        self.entry_pw.grid(row=1, column=1, padx=5, pady=5)

        # 숫자 길이 입력
        ttk.Label(self.root, text="Read Page Num:").grid(row=2, column=0, padx=5, pady=5)
        self.length_var = tk.IntVar(value=1)
        self.length_spinbox = ttk.Spinbox(self.root, values=list(range(1, 11)), width=5, textvariable=self.length_var)
        self.length_spinbox.grid(row=2, column=1, padx=5, pady=5)

        try:
            with open("previous_setting.txt", "r") as f:
                previous_setting = f.read().splitlines()
                self.entry_id.delete(0, tk.END)
                self.entry_id.insert(0, previous_setting[0])
                self.entry_pw.delete(0, tk.END)
                self.entry_pw.insert(0, previous_setting[1])
                self.length_spinbox.delete(0, tk.END)
                self.length_spinbox.set(previous_setting[2])
        except FileNotFoundError:
            pass



        # Remeber 체크박스
        self.remember_var = tk.BooleanVar(value=False)
        self.remember_checkbox = ttk.Checkbutton(self.root, text="Remember", variable=self.remember_var)
        self.remember_checkbox.grid(row=3, column=0, columnspan=2, pady=5)
        
        # 제출 버튼
        self.submit_button = ttk.Button(self.root, text="Submit", command=self.submit_data)
        self.submit_button.grid(row=4, column=0, columnspan=2, pady=20)

        # Previous Setting 버튼
        self.previous_button = ttk.Button(self.root, text="Use Previous Setting", command=self.download_audio)
        self.previous_button.grid(row=5, column=0, columnspan=2, pady=5)

        # Audio 파일 보기
        self.audio_button = ttk.Button(self.root, text="Audio Files", command=self.select_audio)
        self.audio_button.grid(row=6, column=0, columnspan=2, pady=5)

        # 종료 버튼
        self.quit_button = ttk.Button(self.root, text="Quit", command=self.root.destroy)
        self.quit_button.grid(row=7, column=0, columnspan=2, pady=5)

        # GUI 실행
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def select_audio(self):

        try:
            self.root.destroy()
        except tk.TclError:
            pass
        
        option = OptionWindow()
        option.read_audio()

        if option.sel is None:
            return
        
        find_start_time(option.sel)

    def download_audio(self, loaded_class = None):

        if loaded_class is None : loaded_class = DownloadAudio(self.entry_id.get(), self.entry_pw.get())

        try:
            self.root.destroy()
        except tk.TclError:
            pass
        if loaded_class.download_audio() is None:
            return

        self.select_audio()

    def submit_data(self):

        user_id = self.entry_id.get()
        password = self.entry_pw.get()
        length = self.length_var.get()
        remember = self.remember_var.get()

        loaded_class = DownloadAudio(user_id, password)

        self.root.destroy()
        
        if remember:
            with open("previous_setting.txt", "w") as f:
                f.write(f"{user_id}\n{password}\n{length}")

        loaded_class.read_cafe(length)

        self.download_audio(loaded_class)

    def on_closing(self):
        self.root.destroy()

if __name__ == "__main__":
    Main()