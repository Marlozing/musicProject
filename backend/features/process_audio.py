import scipy.io.wavfile as wav

from audio_utils import *

# region 메인 함수

def process_audio(ref_path, mic_path, out_path, alpha=0.5, beta=0.2):
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"원본 파일을 찾을 수 없습니다: {ref_path}")
    if not os.path.exists(mic_path):
        raise FileNotFoundError(f"타겟 파일을 찾을 수 없습니다: {mic_path}")

    # region 1. 오디오 로드 및 정규화
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

    # endregion

    # region 2. 오디오 지연값 탐색 (모노 기준)
    # GCC-PHAT으로 초기값 탐색
    gcc_lag = calculate_gcc_phat(mic_mono, ref_mono)
    # 정밀 보정 (상위 70%만 사용)
    best_lag = refine_lag_robust(ref_mono, mic_mono, initial_lag=gcc_lag, search_range=200)
    # endregion

    # region 3. 오디오 정렬 및 잡음 구간 추출

    # 오디오 정렬
    if ref_full.ndim == 1:
        ref_aligned = align_audio(ref_full, len(mic_full), best_lag)
    else:
        ref_aligned = np.zeros_like(mic_full)
        for ch in range(ref_full.shape[1]):
            ref_aligned[:, ch] = align_audio(ref_full[:, ch], len(mic_full), best_lag)

    # 잡음 구간 추출
    ref_noise, mic_noise = noise_extractor(ref_aligned, mic_full, fs)

    # region 오디오 채널 맞추기
    if mic_noise.ndim == 1:
        # 모노인 경우
        mic_channels = [mic_noise]
        ref_channels = [ref_noise]
    else:
        # 스테레오인 경우 (채널 분리)
        mic_channels = [mic_noise[:, ch] for ch in range(mic_noise.shape[1])]
        # Ref가 모노인데 Mic가 스테레오면 Ref를 복제, 둘 다 스테레오면 분리
        if ref_noise.ndim == 1:
            ref_channels = [ref_noise for _ in range(len(mic_channels))]
        else:
            ref_channels = [ref_noise[:, ch] for ch in range(ref_noise.shape[1])]

    # endregion

    # endregion

    processed_channels = []

    for i in range(len(mic_channels)):
        mic_ch = mic_channels[i]
        ref_ch = ref_channels[i]

        # 고음질 위너 필터 적용
        cleaned_ch = wiener_filter_soft(ref_ch, mic_ch, alpha=alpha, beta=beta)

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
        process_audio("../video/원본.wav", f"../video/[{name}].wav", f"../video/align_[{name}2].wav", alpha=alpha, beta=beta)
        print(f"오디오 처리 완료 in {time.time() - start_time:.2f} seconds.")
    except Exception as e:
        raise RuntimeError(f"오디오 처리 중 치명적인 오류 발생: {e}")