# region Imports
import numpy as np
import scipy.io.wavfile as wav
from scipy import signal
import os

# endregion



# region 정규화 및 보조 함수

# 크거나 같은 2의 제곱수 계산 함수
def next_pow2(n):
    return 1 << (int(n - 1).bit_length())


# 오디오 정규화 함수
def robust_normalize(data):
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128.0) / 128.0

    data = data.astype(np.float32)

    # 오디오의 최대 절대값을 1로 정규화
    max_val = np.max(np.abs(data))
    if max_val > 1e-5: data = data / max_val
    return data


# endregion

# region 정렬 관련 함수들

# region gcc-phat 함수

def calculate_gcc_phat(x, y):
    # FFT 크기 계산
    n = len(x) + len(y) - 1
    n_fft = next_pow2(n)

    # FFT 수행
    X = np.fft.rfft(x, n=n_fft)
    Y = np.fft.rfft(y, n=n_fft)

    # PHAT 가중치를 적용한 상호 전력 스펙트럼
    G = X * np.conj(Y)
    R = G / (np.abs(G) + 1e-12)

    # 역 FFT로 상호 상관 함수 계산
    cc = np.fft.irfft(R, n=n_fft)

    # 지연이 0인 지점을 중심으로 재정렬
    half = n_fft // 2
    cc_lin = np.concatenate((cc[-half:], cc[:half + 1]))
    k = int(np.argmax(cc_lin))

    # 서브 샘플 보간 (정밀도 향상)
    delta = 0.0
    if 0 < k < len(cc_lin) - 1:
        y1, y2, y3 = cc_lin[k - 1], cc_lin[k], cc_lin[k + 1]
        d = (y1 - 2 * y2 + y3)
        delta = 0.0 if abs(d) < 1e-20 else 0.5 * (y1 - y3) / d
        delta = float(np.clip(delta, -0.5, 0.5))

    lag_samples = (k + delta) - (len(cc_lin) - 1) / 2.0
    return int(round(lag_samples))


# endregion

# region 정밀 지연 보정 함수

def refine_lag_robust(ref, mic, initial_lag, search_range=200, keep_ratio=0.7):
    n_ref = len(ref)
    center = initial_lag
    lags = range(center - search_range, center + search_range + 1)

    # 효율적인 뷰 생성을 위한 선행 패딩
    pad_size = abs(center) + search_range + 1000
    mic_padded = np.pad(mic, (pad_size, pad_size), 'constant')

    # 속도 최적화를 위해 앞부분 30초만 비교
    compare_len = min(n_ref, 16000 * 30)
    ref_comp = ref[:compare_len]
    k = int(compare_len * keep_ratio)  # 하위 70% 인덱스

    best_lag = center
    min_error = float('inf')

    for lag in lags:
        start = pad_size + lag
        end = start + compare_len
        mic_view = mic_padded[start:end]

        if len(mic_view) < compare_len: continue

        # L1 오차 계산
        diff = np.abs(mic_view - ref_comp)

        # 하위 70% 오차만 합산 (목소리 제외)
        partitioned = np.partition(diff, k)
        err = np.sum(partitioned[:k])

        if err < min_error:
            min_error = err
            best_lag = lag

    return best_lag


# endregion

# region 오디오 정렬 함수

def align_ref_to_mic_canvas(ref, mic_len, lag):
    ref_aligned = np.zeros(mic_len, dtype=np.float32)
    n_ref = len(ref)

    start_idx = lag

    # 복사 범위 계산
    r_start = max(0, -start_idx)
    r_end = min(n_ref, mic_len - start_idx)
    m_start = max(0, start_idx)
    m_end = min(mic_len, start_idx + n_ref)

    copy_len = min(r_end - r_start, m_end - m_start)

    if copy_len > 0:
        ref_aligned[m_start: m_start + copy_len] = ref[r_start: r_start + copy_len]

    return ref_aligned


# endregion

# endregion

# region 잡음 구간 추출 함수
def audio_extractor(ref, mic, sr, output_dir,
                              threshold=0.3, min_duration=0.5, padding_sec=1.0):
    # 1. 분석용 데이터 전처리
    print(f"[Step 1] 데이터 전처리 중...")

    total_duration = ref.shape[0] / sr

    # 분석용 (다운샘플링)
    y_sr = sr // 2
    y_ref = ref[::y_sr]
    y_mic = mic[::y_sr]

    if y_ref.ndim == 2: y_ref = y_ref.mean(axis=1)
    if y_mic.ndim == 2: y_mic = y_mic.mean(axis=1)

    # 2. 잡음 구간 탐색
    print(f"[Step 2] 잡음 구간 탐색 중...")

    min_len = min(len(y_ref), len(y_mic))
    ref_cut = y_ref[:min_len]
    mic_cut = y_mic[:min_len]

    # 스펙트로그램 계산
    _, _, Z_ref = signal.stft(ref_cut, fs=y_sr, nperseg=512)
    _, _, Z_mic = signal.stft(mic_cut, fs=y_sr, nperseg=512)

    # 스펙트로그램 정규화
    S_ref_norm = np.abs(Z_ref) / (np.max(np.abs(Z_ref)) + 1e-9)
    S_mic_norm = np.abs(Z_mic) / (np.max(np.abs(Z_mic)) + 1e-9)

    # 잡음 계샨
    diff = np.maximum(0, S_ref_norm - S_mic_norm)
    noise_profile = np.mean(diff, axis=0)

    # 그래프 스무딩 및 정규화
    window_size = 5
    noise_profile = np.convolve(noise_profile, np.ones(window_size) / window_size, mode='same')
    noise_profile = (noise_profile - np.min(noise_profile)) / (np.max(noise_profile) + 1e-9)
    # 가로축 시간으로 변환
    t_axis = np.arange(len(noise_profile)) * (512 / sr / 2)

    # region 임계값 초과 구간 탐색
    is_noisy = noise_profile > threshold

    intervals = []
    start_t = None

    for i, val in enumerate(is_noisy):
        if val:
            if start_t is None: start_t = t_axis[i]
        else:
            if start_t is not None:
                end_t = t_axis[i]
                if end_t - start_t >= min_duration:
                    intervals.append((start_t, end_t))
                start_t = None
    if start_t is not None:
        intervals.append((start_t, t_axis[-1]))
    # endregion

    # region 구간 병합 및 패딩 적용
    final_intervals = []
    if intervals:
        intervals.sort()
        padded = []
        for s, e in intervals:
            padded.append((max(0, s - padding_sec), min(total_duration, e + padding_sec)))

        merged = [padded[0]]
        for curr_s, curr_e in padded[1:]:
            last_s, last_e = merged[-1]
            if curr_s <= last_e:
                merged[-1] = (last_s, max(last_e, curr_e))
            else:
                merged.append((curr_s, curr_e))
        final_intervals = merged
    # endregion

    if not final_intervals:
        print("잡음 구간 없음.")
        return

    print(f"   -> 최종 구간: {len(final_intervals)}개")

    # 3. 저장
    print(f"[Step 3] 결과 저장 중 (tmp_mic.wav, tmp_lpb.wav)...")

    # 출력 변수 할당
    y_out_ref = np.zeros_like(full_data_ref)
    y_out_mic = np.zeros_like(full_data_mic)

    fade_len = int(0.01 * full_sr_ref)

    # region 잡음 부분 추출 및 페이드 인/아웃 적용
    for s_sec, e_sec in final_intervals:
        s_idx = int(s_sec * full_sr_ref)
        e_idx = int(e_sec * full_sr_ref)

        s_idx = max(0, s_idx)
        e_idx = min(min(len(full_data_ref), len(full_data_mic)), e_idx)

        if s_idx >= e_idx: continue

        # Ref 복사
        if full_data_ref.ndim == 2:
            seg_ref = full_data_ref[s_idx:e_idx, :].copy()
            if len(seg_ref) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len).reshape(-1, 1)
                seg_ref[:fade_len] *= fade  # 이제 float *= float 이라 에러 없음
                seg_ref[-fade_len:] *= fade[::-1]
            y_out_ref[s_idx:e_idx, :] = seg_ref
        else:
            seg_ref = full_data_ref[s_idx:e_idx].copy()
            if len(seg_ref) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len)
                seg_ref[:fade_len] *= fade
                seg_ref[-fade_len:] *= fade[::-1]
            y_out_ref[s_idx:e_idx] = seg_ref

        # Mic 복사
        if full_data_mic.ndim == 2:
            seg_mic = full_data_mic[s_idx:e_idx, :].copy()
            if len(seg_mic) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len).reshape(-1, 1)
                seg_mic[:fade_len] *= fade
                seg_mic[-fade_len:] *= fade[::-1]
            y_out_mic[s_idx:e_idx, :] = seg_mic
        else:
            seg_mic = full_data_mic[s_idx:e_idx].copy()
            if len(seg_mic) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len)
                seg_mic[:fade_len] *= fade
                seg_mic[-fade_len:] *= fade[::-1]
            y_out_mic[s_idx:e_idx] = seg_mic
    # endregion

    return y_out_ref, y_out_mic

# endregion