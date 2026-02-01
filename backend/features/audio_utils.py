# region Imports
import numpy as np
import scipy.io.wavfile as wav
from scipy import signal
import os
from numba import jit
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

def align_audio(ref, mic_len, lag):
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
def noise_extractor(ref, mic, fs,
                              threshold=0.01, min_duration=0.1, padding_sec=0.1):
    # 1. 분석용 데이터 전처리
    print(f"[Step 1] 데이터 전처리 중...")

    total_duration = ref.shape[0] / fs

    # 분석용 (다운샘플링)
    step = 2
    data_fs = fs // step
    data_ref = ref[::step]
    data_mic = mic[::step]

    if data_ref.ndim == 2: data_ref = data_ref.mean(axis=1)
    if data_mic.ndim == 2: data_mic = data_mic.mean(axis=1)

    # 2. 잡음 구간 탐색
    print(f"[Step 2] 잡음 구간 탐색 중...")

    min_len = min(len(data_ref), len(data_mic))
    ref_cut = data_ref[:min_len]
    mic_cut = data_mic[:min_len]

    # 스펙트로그램 계산
    _, _, Z_ref = signal.stft(ref_cut, fs=data_fs, nperseg=512)
    _, _, Z_mic = signal.stft(mic_cut, fs=data_fs, nperseg=512)

    # 스펙트로그램 정규화
    S_ref_norm = np.abs(Z_ref) / (np.max(np.abs(Z_ref)) + 1e-9)
    S_mic_norm = np.abs(Z_mic) / (np.max(np.abs(Z_mic)) + 1e-9)

    # 잡음 계샨
    diff = np.maximum(0, S_mic_norm - S_ref_norm)
    noise_profile = np.mean(diff, axis=0)

    # 그래프 스무딩 및 정규화
    window_size = 5
    noise_profile = np.convolve(noise_profile, np.ones(window_size) / window_size, mode='same')
    noise_profile = (noise_profile - np.min(noise_profile)) / (np.max(noise_profile) + 1e-9)
    # 가로축 시간으로 변환
    t_axis = np.arange(len(noise_profile)) * (512 / data_fs / 2)

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

    # 출력 변수 할당
    y_out_ref = np.zeros_like(ref)
    y_out_mic = np.zeros_like(mic)

    fade_len = int(0.01 * fs)

    # region 잡음 부분 추출 및 페이드 인/아웃 적용
    for s_sec, e_sec in final_intervals:
        s_idx = int(s_sec * fs)
        e_idx = int(e_sec * fs)

        s_idx = max(0, s_idx)
        e_idx = min(min(len(ref), len(mic)), e_idx)

        if s_idx >= e_idx: continue

        # Ref 복사
        if ref.ndim == 2:
            seg_ref = ref[s_idx:e_idx, :].copy()
            if len(seg_ref) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len).reshape(-1, 1)
                seg_ref[:fade_len] *= fade  # 이제 float *= float 이라 에러 없음
                seg_ref[-fade_len:] *= fade[::-1]
            y_out_ref[s_idx:e_idx, :] = seg_ref
        else:
            seg_ref = ref[s_idx:e_idx].copy()
            if len(seg_ref) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len)
                seg_ref[:fade_len] *= fade
                seg_ref[-fade_len:] *= fade[::-1]
            y_out_ref[s_idx:e_idx] = seg_ref

        # Mic 복사
        if mic.ndim == 2:
            seg_mic = mic[s_idx:e_idx, :].copy()
            if len(seg_mic) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len).reshape(-1, 1)
                seg_mic[:fade_len] *= fade
                seg_mic[-fade_len:] *= fade[::-1]
            y_out_mic[s_idx:e_idx, :] = seg_mic
        else:
            seg_mic = mic[s_idx:e_idx].copy()
            if len(seg_mic) > fade_len * 2:
                fade = np.linspace(0, 1, fade_len)
                seg_mic[:fade_len] *= fade
                seg_mic[-fade_len:] *= fade[::-1]
            y_out_mic[s_idx:e_idx] = seg_mic
    # endregion

    return y_out_ref, y_out_mic

# endregion


# region 배경음 제거 함수

def wiener_filter_soft(ref, mic, alpha, beta):
    # 고해상도 설정
    N_FFT = 4096
    HOP_LENGTH = 512 #128

    # 스펙트로그램 생성
    f, t, Z_ref = signal.stft(ref, nperseg=N_FFT, noverlap=N_FFT - HOP_LENGTH)
    _, _, Z_mic = signal.stft(mic, nperseg=N_FFT, noverlap=N_FFT - HOP_LENGTH)

    P_ref = np.abs(Z_ref) ** 2
    P_mic = np.abs(Z_mic) ** 2 + 1e-12

    subtracted_power = P_mic - (alpha * P_ref)

    floor = P_mic * beta
    P_estimated = np.maximum(subtracted_power, floor)

    mask = P_estimated / P_mic
    mask = np.sqrt(mask)

    Z_clean = Z_mic * mask
    _, clean_audio = signal.istft(Z_clean, nperseg=N_FFT, noverlap=N_FFT - HOP_LENGTH)

    # ISTFT 후 길이 보정
    if len(clean_audio) > len(mic):
        clean_audio = clean_audio[:len(mic)]
    elif len(clean_audio) < len(mic):
        clean_audio = np.pad(clean_audio, (0, len(mic) - len(clean_audio)), 'constant')

    return clean_audio


# endregion

# region 후처리 함수

# region 파이썬 -> 기계어 함수

@jit(nopython=True, cache=True)
def _calculate_gain_curve_jit(abs_audio, threshold_linear, ratio, gain_decay, env_decay):
    n_samples = len(abs_audio)
    gain_curve = np.zeros(n_samples, dtype=np.float32)
    current_env = 0.0
    current_gain = 1.0

    for i in range(n_samples):
        # 엔벨로프 추적 (빠른 반응)
        val = abs_audio[i]
        if val > current_env:
            current_env = val
        else:
            current_env = current_env * env_decay + val * (1.0 - env_decay)

        # 목표 게인 설정
        if current_env > threshold_linear:
            target_gain = 1.0
        else:
            target_gain = ratio

        # 게인 적용 (Attack은 즉시, Release는 천천히)
        if target_gain > current_gain:
            current_gain = target_gain  # Attack
        else:
            current_gain = current_gain * gain_decay  # Release
            if current_gain < ratio: current_gain = ratio

        gain_curve[i] = current_gain

    return gain_curve

# endregion

def apply_soft_expander(audio, threshold_db=-45.0, ratio=0.2, release_ms=400, fs=48000):
    threshold_linear = 10 ** (threshold_db / 20)

    # Numba 처리를 위해 float32 타입 보장
    abs_audio = np.abs(audio).astype(np.float32)

    # 감쇠 계수 계산 (문 닫는 속도)
    if release_ms > 0:
        release_samples = int((release_ms / 1000) * fs)
        gain_decay = np.exp(-1.0 / release_samples)
    else:
        gain_decay = 0.0

    # 엔벨로프 추적용 감쇠 계수 (센서 반응 속도 - 10ms 고정)
    env_decay = np.exp(-1.0 / (fs * 0.01))

    # [변경] 분리된 Numba JIT 함수 호출 (속도 가속 구간)
    gain_curve = _calculate_gain_curve_jit(abs_audio, threshold_linear, ratio, gain_decay, env_decay)

    # 팝 노이즈 방지용 추가 스무딩 (Numpy Convolve는 이미 빠르므로 유지)
    kernel_size = 500
    gain_curve_smooth = np.convolve(gain_curve, np.ones(kernel_size) / kernel_size, mode='same')

    return audio * gain_curve_smooth


# endregion

# endregion