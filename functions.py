import numpy as np
import scipy.signal as signal
def separate(path):
    import os

    if not os.path.exists("separated"):
        os.makedirs("separated")

    '''
    separator = demucs.api.Separator()

    _, separated = separator.separate_audio_file("audio/"+path+".wav")

    background = separated["bass"] + separated["drums"] + separated["other"]

    demucs.api.save_audio(background, "separated/"+path+".wav", 44100)'''

def optimize_audio_ratio(audio1, audio2, tolerance=10**5, max_iterations=1000, learning_rate=0.1, debug=False):
    if len(audio2) > len(audio1):
        audio2 = audio2[:len(audio1)]

    # 초기 비율 설정
    ratio = 2.0

    for iteration in range(max_iterations):
        # 현재 차이 계산
        diff = np.sum(np.square(audio1 - audio2 * ratio))

        if debug:
            print(f"Iteration: {iteration}, 비율: {ratio:.4f}, 차이: {diff:.4f}")

        # 차이가 허용 오차 이하일 경우 종료
        if diff < tolerance:
            break

        # Gradient 계산
        error = audio1 - audio2 * ratio
        gradient = -2 * np.sum(audio2 * error)  # Gradient 계산

        # 비율 업데이트
        ratio -= learning_rate * gradient / len(audio1)  # 평균을 내어 안정성 증가

        # 비율 범위 제한
        ratio = max(0.1, min(ratio, 3.0))  # 비율이 0.1 이상, 3.0 이하로 제한

    if debug:
        print(f"최종 비율: {ratio:.4f}, 최종 차이: {diff:.4f}")

    return ratio

if __name__ == "__main__":
    from uvr import models
    from uvr.utils.get_models import download_all_models
    import torch
    import librosa
    import audiofile
    import json

    models_json = json.load(open("ultimatevocalremover_api/src/models_dir/models.json", "r"))
    download_all_models(models_json)
    name = "audio/[우왁굳].wav"
    origin, _ = librosa.load(name)
    device = "cuda"

    demucs = models.MDXC(name="hdemucs_mmi", other_metadata={"segment": 2, "split": True}, device=device, logger=None)

    # Separating an audio file
    res = demucs(name)

    vocals = res["vocals"]

    audiofile.write("vocals.wav", vocals, 44100)