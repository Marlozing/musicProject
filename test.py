from waveform_adjuster import Adjuster
from functions import *

import librosa
import matplotlib.pyplot as plt

name = "[우왁굳]"
sr = 44100

test_audio1, _ = librosa.load("separated/원본.wav", sr=sr)
test_audio2, _ = librosa.load("separated/"+name+".wav", sr=sr)

audio1, _ = librosa.load("audio/원본.wav", sr=sr)
audio2, _ = librosa.load("audio/"+name+".wav", sr=sr)

# AudioVisualizer 클래스 인스턴스 생성
visualizer = Adjuster(test_audio1, test_audio2)

# 그래프 표시
visualizer.show()

start_index = -236 #visualizer.final_index

if start_index is not None:
    if start_index < 0:
        audio2 = np.pad(audio2, (abs(start_index), 0), 'constant')
    else:
        audio2 = audio2[start_index:]

    print(np.sum(audio1), np.sum(audio2[:len(audio1)]), np.sum(audio1) / np.sum(audio2[:len(audio1)]))

    #multiply = optimize_audio_ratio(audio1, audio2)
    #print(multiply)
    #audio2 = audio2 * multiply

    '''
    # 시각화
    plt.figure(figsize=(12, 6))
    plt.plot(audio1, label='audio1')
    plt.plot(audio2, label='audio2')
    plt.plot(audio2[:len(audio1)] - audio1, label='audio1 - audio2')
    plt.legend()
    plt.show()

    import soundfile as sf
    sf.write('output.wav', audio2[:len(audio1)] - audio1, 44100)
    '''