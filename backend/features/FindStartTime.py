import librosa
import numpy as np
import ray
from sklearn.model_selection import ParameterGrid

# region ray 초기화
ray.init()
# endregion


# region HyperDTW
async def hyper_dtw(mfcc_1, mfcc_2, param_grid):
    min_distance = float("inf")
    best_index = -1

    tasks = []  # Ray 태스크들을 저장할 리스트
    indices = []  # 각 태스크의 시작 인덱스를 저장

    # 각 파라미터 조합에 대해 DTW 계산을 수행 (현재 param_grid가 비어 있다면 한 번만 실행)
    for params in list(ParameterGrid(param_grid)):
        # mfcc_1의 길이와 mfcc_2의 길이에 따라 시작 인덱스 범위 계산
        max_start = mfcc_2.shape[1] - mfcc_1.shape[1] + 1
        for start_index in range(max_start):
            # mfcc_2의 해당 구간 슬라이스 얻기
            mfcc_2_slice = mfcc_2[:, start_index : start_index + mfcc_1.shape[1]]
            # Ray remote task 생성 (비동기 태스크)
            task = compute_dtw.remote(mfcc_1, mfcc_2_slice)
            tasks.append(task)
            indices.append(start_index)

    # 모든 태스크를 한 번에 실행하고 결과를 받아옴
    distances = ray.get(tasks)

    # 각 슬라이스별로 DTW 거리 결과를 확인하여 최솟값과 인덱스 결정
    for idx, distance in zip(indices, distances):
        if distance < min_distance:
            min_distance = distance
            best_index = idx

    return best_index


# endregion


# region DTW 병렬 처리
@ray.remote
def compute_dtw(mfcc_1, mfcc_2_slice):
    # MFCC 정규화
    mfcc_1_normalized = (mfcc_1 - np.mean(mfcc_1)) / np.std(mfcc_1)
    mfcc_2_slice_normalized = (mfcc_2_slice - np.mean(mfcc_2_slice)) / np.std(
        mfcc_2_slice
    )

    # DTW 거리 계산
    distance, _ = librosa.sequence.dtw(mfcc_1_normalized.T, mfcc_2_slice_normalized.T)
    return distance[-1, -1]  # 최종 거리 반환


# endregion


# region 오디오 시간 찾기
async def find_time(origin_audio, reaction_audio):

    param_grid = {}
    compiled_origin = origin_audio[: 20 * 44100] / np.max(np.abs(origin_audio))
    compiled_reaction = reaction_audio[: 2 * 60 * 44100] / np.max(
        np.abs(reaction_audio)
    )

    # MFCC 특징 추출
    mfcc_origin = librosa.feature.mfcc(y=compiled_origin, sr=44100, n_mfcc=13)
    mfcc_reaction = librosa.feature.mfcc(y=compiled_reaction, sr=44100, n_mfcc=13)

    best_index = await hyper_dtw(mfcc_origin, mfcc_reaction, param_grid)
    return best_index


# endregion
