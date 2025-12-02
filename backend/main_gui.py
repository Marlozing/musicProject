import sys
import os
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                               QLabel, QFileDialog, QMessageBox, QGroupBox, QLineEdit, QHBoxLayout)
from PySide6.QtCore import QThread, Signal, Qt
import features.align_audio


class WorkerThread(QThread):
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, ref_path, mic_path, out_path):
        super().__init__()
        self.ref_path = ref_path
        self.mic_path = mic_path
        self.out_path = out_path

    def run(self):
        try:
            # 함수 이름 변경 반영 (align_and_process)
            audio_processor.align_and_process(self.ref_path, self.mic_path, self.out_path)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class AudioCleanerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video/Audio Cleaner Pro")
        self.setGeometry(100, 100, 600, 280)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        file_group = QGroupBox("파일 선택")
        file_layout = QVBoxLayout()

        self.ref_input = self.create_file_input("원본 (배경음/MR):", file_layout)
        self.mic_input = self.create_file_input("타겟 (반응 영상/오디오):", file_layout)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        self.btn_run = QPushButton("배경음 제거 및 영상 저장 (Start)")
        self.btn_run.setFixedHeight(50)
        self.btn_run.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #0078D7; color: white;")
        self.btn_run.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_run)

        self.status_label = QLabel("준비됨")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def create_file_input(self, label_text, parent_layout):
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit()
        line_edit.setReadOnly(True)
        btn = QPushButton("찾기...")
        btn.clicked.connect(lambda: self.open_file_dialog(line_edit))

        h_layout.addWidget(label)
        h_layout.addWidget(line_edit)
        h_layout.addWidget(btn)
        parent_layout.addLayout(h_layout)
        return line_edit

    def open_file_dialog(self, line_edit_widget):
        # 비디오/오디오 모두 필터링
        filter_str = "Media Files (*.mp4 *.mkv *.avi *.mov *.webm *.wav *.mp3 *.m4a);;All Files (*.*)"
        fname, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", filter_str)
        if fname:
            line_edit_widget.setText(fname)

    def start_processing(self):
        ref_path = self.ref_input.text()
        mic_path = self.mic_input.text()

        if not ref_path or not mic_path:
            QMessageBox.warning(self, "경고", "파일을 모두 선택해주세요.")
            return

        # 출력 파일명 및 확장자 자동 결정
        folder = os.path.dirname(mic_path)
        base_name = os.path.splitext(os.path.basename(mic_path))[0]
        ext = os.path.splitext(mic_path)[1].lower()  # 원본 확장자 유지 (.mp4 -> .mp4)

        # 만약 비디오 확장자가 아니면 기본 wav로 저장 (오디오인 경우)
        if ext not in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            ext = '.wav'

        out_path = os.path.join(folder, f"{base_name}_Cleaned{ext}")

        self.btn_run.setEnabled(False)
        self.btn_run.setText("처리 중... (영상 렌더링은 시간이 걸립니다)")
        self.status_label.setText("오디오 분리 및 비디오 병합 중...")

        self.worker = WorkerThread(ref_path, mic_path, out_path)
        self.worker.finished_signal.connect(lambda: self.on_finished(out_path))
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def on_finished(self, out_path):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("배경음 제거 및 영상 저장 (Start)")
        self.status_label.setText(f"완료! 저장됨: {os.path.basename(out_path)}")
        QMessageBox.information(self, "성공", f"작업 완료!\n\n저장 위치:\n{out_path}")

    def on_error(self, err_msg):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("배경음 제거 및 영상 저장 (Start)")
        self.status_label.setText("오류 발생")
        QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다:\n{err_msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AudioCleanerApp()
    window.show()
    sys.exit(app.exec())