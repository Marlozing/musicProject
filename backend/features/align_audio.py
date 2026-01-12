import numpy as np
import scipy.io.wavfile as wav
from scipy import signal
import os
from numba import jit  # Numba 임포트
from audio_utils import robust_normalize, calculate_gcc_phat, refine_lag_robust, align_ref_to_mic_canvas

# region 배경음 제거 함수

def wiener_filter_soft(ref, mic, alpha, beta):
    # 고해상도 설정
    N_FFT = 4096
    HOP_LENGTH = 512 #128

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

# region 메인 함수

def align_audio(ref_path, mic_path, out_path, alpha=0.5, beta=0.2):
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"원본 파일을 찾을 수 없습니다: {ref_path}")
    if not os.path.exists(mic_path):
        raise FileNotFoundError(f"타겟 파일을 찾을 수 없습니다: {mic_path}")

    fs_ref, data_ref = wav.read(ref_path)
    fs_mic, data_mic = wav.read(mic_path)

    if fs_ref != fs_mic:
        raise ValueError(f"샘플링 레이트가 일치하지 않습니다. (Ref: {fs_ref}, Mic: {fs_mic})")

    fs = fs_mic

    # 스테레오를 모노로 변환 (정렬 계산용)
    if data_ref.ndim > 1:
        data_ref_mono = np.mean(data_ref, axis=1)
    else:
        data_ref_mono = data_ref

    if data_mic.ndim > 1:
        data_mic_mono = np.mean(data_mic, axis=1)
    else:
        data_mic_mono = data_mic

    # 정규화 (정렬 계산용 모노 데이터)
    ref_mono = robust_normalize(data_ref_mono)
    mic_mono = robust_normalize(data_mic_mono)

    # 실제 처리를 위한 원본 정규화 (채널 유지)
    ref_full = robust_normalize(data_ref)
    mic_full = robust_normalize(data_mic)

    # 2. 정렬 (Alignment)
    # GCC-PHAT으로 초기값 탐색 (모노 기준)
    gcc_lag = calculate_gcc_phat(mic_mono, ref_mono)
    # 이상치 제거를 통한 정밀 보정 (모노 기준)
    best_lag = refine_lag_robust(ref_mono, mic_mono, initial_lag=gcc_lag, search_range=200)

    # 3. 분리 및 후처리 (채널별 처리)
    # 입력이 스테레오인 경우 채널별로 분리하여 처리
    if mic_full.ndim == 1:
        # 모노인 경우
        mic_channels = [mic_full]
        ref_channels = [ref_full]
    else:
        # 스테레오인 경우 (채널 분리)
        mic_channels = [mic_full[:, ch] for ch in range(mic_full.shape[1])]
        # Ref가 모노인데 Mic가 스테레오면 Ref를 복제, 둘 다 스테레오면 분리
        if ref_full.ndim == 1:
            ref_channels = [ref_full for _ in range(len(mic_channels))]
        else:
            ref_channels = [ref_full[:, ch] for ch in range(ref_full.shape[1])]

    processed_channels = []

    for i in range(len(mic_channels)):
        mic_ch = mic_channels[i]
        ref_ch = ref_channels[i]

        # 캔버스 정렬 (채널별)
        ref_aligned = align_ref_to_mic_canvas(ref_ch, len(mic_ch), best_lag)

        # 고음질 위너 필터 적용
        cleaned_ch = wiener_filter_soft(ref_aligned, mic_ch, alpha=alpha, beta=beta)

        # ISTFT 후 길이 보정
        if len(cleaned_ch) > len(mic_ch):
            cleaned_ch = cleaned_ch[:len(mic_ch)]
        elif len(cleaned_ch) < len(mic_ch):
            cleaned_ch = np.pad(cleaned_ch, (0, len(mic_ch) - len(cleaned_ch)), 'constant')

        # 후처리 (소프트 익스팬더) - Numba 적용으로 가속됨
        final_ch = apply_soft_expander(cleaned_ch, threshold_db=-45.0, ratio=0.2, release_ms=400, fs=fs)

        processed_channels.append(final_ch)

    # 채널 병합
    if len(processed_channels) > 1:
        final_audio = np.stack(processed_channels, axis=1)
    else:
        final_audio = processed_channels[0]

    # 5. 저장
    wav.write(out_path, fs, np.int16(final_audio * 32767))


# endregion

if __name__ == "__main__":
    import time

    name = "비챤"
    alpha = 0.5
    beta = 0.2

    start_time = time.time()


    try:
        align_audio("../video/원본.wav", f"../video/[{name}].wav", f"../video/align_[{name}2].wav", alpha=alpha, beta=beta)
        print(f"오디오 처리 완료 in {time.time() - start_time:.2f} seconds.")
    except Exception as e:
        raise RuntimeError(f"오디오 처리 중 치명적인 오류 발생: {e}")