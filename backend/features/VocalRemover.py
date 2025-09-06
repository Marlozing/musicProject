import os
import logging
import numpy as np
import soundfile as sf

from spleeter.separator import Separator

# region 특정 경고 무시
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
logging.getLogger("tensorflow").setLevel(logging.ERROR)
# endregion


class VocalRemover:
    # region 초기 설정
    def __init__(self, output_dir):
        self.output_dir = output_dir

        print("Loading Spleeter Model...")
        self.separator = Separator("spleeter:2stems")
        print("Spleeter Model Loading Completed.")

    # endregion

    # region 오디오 파일 로드
    def _load_audio(self, path):
        y, _ = sf.read(path, dtype="float32")

        # If stereo or multi-channel, convert to mono by averaging channels
        if y.ndim > 1:
            y = y.mean(axis=1)

        # Ensure it's (samples, 1) for Spleeter's (T, C) format where C=1
        y = np.expand_dims(y, axis=1)

        return y.astype(np.float32)

    # endregion

    # region 보컬 제거
    def separate_other(self, input_path):
        if not os.path.isfile(input_path):
            print(f"File Not Found : {input_path}")
            return

        try:
            base_name = input_path.split("/")[-1].split(".")[0]
            output_file_name = f"{base_name}_other.wav"
            output_path = os.path.join(self.output_dir, output_file_name)

            # 오디오 로드
            waveform = self._load_audio(input_path)

            # 분리 작업 수행
            stems = self.separator.separate(waveform)
            other_track = stems["accompaniment"]

            # 보컬 제거된 오디오 저장
            sf.write(output_path, other_track, 44100, subtype="PCM_16")
            print(f"{input_path} -> {output_path}")

        except Exception as e:
            print(f"Error occurred during processing {input_path} : {e}")

    # endregion


if __name__ == "__main__":
    output_base_dir = "./video/sep"
    input_path = "./video/[비챤].wav"

    processor = VocalRemover(output_base_dir)
    processor.separate_other(input_path)