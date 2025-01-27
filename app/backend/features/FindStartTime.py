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

    # 하이퍼파라미터 그리드 탐색
    for _ in ParameterGrid(param_grid):
        for start_index in range(mfcc_2.shape[1] - mfcc_1.shape[1] + 1):
            mfcc_2_slice = mfcc_2[:, start_index : start_index + mfcc_1.shape[1]]
            distance = ray.get(compute_dtw.remote(mfcc_1, mfcc_2_slice))  # await 제거

            # 최단 거리 찾기
            if distance < min_distance:
                min_distance = distance
                best_index = start_index

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
    best_index = 0
    compiled_origin = origin_audio[: 20 * 44100] / np.max(np.abs(origin_audio))
    compiled_reaction = reaction_audio[: 2 * 60 * 44100] / np.max(
        np.abs(reaction_audio)
    )

    # MFCC 특징 추출
    mfcc_origin = librosa.feature.mfcc(
        y=compiled_origin, sr=44100, n_mfcc=13
    )
    mfcc_reaction = librosa.feature.mfcc(
        y=compiled_reaction, sr=44100, n_mfcc=13
    )
    best_index = await hyper_dtw(mfcc_origin, mfcc_reaction, param_grid)
    print(best_index)
    return best_index


# endregion