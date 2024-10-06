import numpy as np
import ray
import librosa
from sklearn.model_selection import ParameterGrid

ray.init(object_store_memory=4 * 1024 * 1024 * 1024,dashboard_port=None)

# HyperDTW 구현
def hyper_dtw(mfcc_1, mfcc_2, param_grid):
    """HyperDTW를 이용한 두 mfcc의 최단거리 추출"""
    min_distance = float('inf')
    best_index = -1

    # 하이퍼파라미터 그리드 탐색
    for _ in ParameterGrid(param_grid):
        for start_index in range(mfcc_2.shape[1] - mfcc_1.shape[1] + 1):
            mfcc_2_slice = mfcc_2[:, start_index:start_index + mfcc_1.shape[1]]
            distance = ray.get(compute_dtw.remote(mfcc_1, mfcc_2_slice))

            # 최단 거리 찾기
            if distance < min_distance:
                min_distance = distance
                best_index = start_index

    return best_index


@ray.remote
def compute_dtw(mfcc_1, mfcc_2_slice):
    """DTW 병렬 처리"""
    # MFCC 정규화
    mfcc_1_normalized = (mfcc_1 - np.mean(mfcc_1)) / np.std(mfcc_1)
    mfcc_2_slice_normalized = (mfcc_2_slice - np.mean(mfcc_2_slice)) / np.std(mfcc_2_slice)

    # DTW 거리 계산
    distance, _ = librosa.sequence.dtw(mfcc_1_normalized.T, mfcc_2_slice_normalized.T)
    return distance[-1, -1]  # 최종 거리 반환


def find_time(audio1, audio2):
    param_grid = {

    }
    sr = 44100

    compiled_audio1 = audio1[:20 * sr] / np.max(np.abs(audio1))
    compiled_audio2 = audio2[:2 * 60 * sr] / np.max(np.abs(audio2))

    # MFCC 특징 추출
    mfcc_1 = librosa.feature.mfcc(y=compiled_audio1, sr=sr, n_mfcc=13)
    mfcc_2 = librosa.feature.mfcc(y=compiled_audio2, sr=sr, n_mfcc=13)
    best_index = hyper_dtw(mfcc_1, mfcc_2, param_grid)

    return best_index


if __name__ == '__main__':
    y_1, _ = librosa.load('audio/원본.wav', sr=None)
    y_2, _ = librosa.load('audio/[아이네].wav', sr=None)

    print(find_time(y_1, y_2) * 512)
