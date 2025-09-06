import librosa
import numpy as np
import soundfile as sf
from numpy.fft import rfft, irfft, rfftfreq
from scipy.signal import butter, filtfilt, correlate, correlation_lags, get_window
import time

EPS = 1e-12


# region 피처(정렬용): Chroma CQT 프레임 L2 정규화
def chroma_feat(y, sr, hop=512):
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)  # [12, T]
    denom = np.linalg.norm(C, axis=0, keepdims=True) + EPS
    Cn = C / denom
    return np.where(np.isfinite(Cn), Cn, 0.0)


# endregion

# region FFT 기반 멀티채널 슬라이딩 코사인 유사도(정렬용)
def sliding_cosine_similarity_multi(H, N):
    C, Th = H.shape
    _, Tn = N.shape
    if Tn > Th:
        raise ValueError("needle 프레임 수가 haystack보다 큼")
    nfft = 1 << int(np.ceil(np.log2(Th + Tn - 1)))
    num_full = None
    for c in range(C):
        h = H[c]
        nrev = N[c, ::-1]
        Hf = rfft(h, n=nfft)
        Nf = rfft(nrev, n=nfft)
        conv = irfft(Hf * Nf, n=nfft)[:Th + Tn - 1]
        num_full = conv if num_full is None else (num_full + conv)
    num = num_full[Tn - 1:Th]
    N_norm2 = float(np.sum(N ** 2))
    H_norm2_per_frame = np.sum(H ** 2, axis=0)
    kernel = np.ones(Tn)
    H_sum = irfft(rfft(H_norm2_per_frame, n=nfft) * rfft(kernel[::-1], n=nfft), n=nfft)[:Th + Tn - 1]
    H_valid = H_sum[Tn - 1:Th] + EPS
    denom = np.sqrt(H_valid * (N_norm2 + EPS)) + EPS
    sim = num / denom
    return np.where(np.isfinite(sim), sim, 0.0)


# endregion

# region 후보 선택: Top-1 (NMS 간단 적용)
def pick_top1_with_nms(sim, Tn, nms_ratio=0.6):
    sim = np.asarray(sim)
    if sim.size == 0:
        return 0
    idxs = np.argsort(sim)[::-1]
    suppress = np.zeros_like(sim, dtype=bool)
    min_sep = max(1, int(Tn * nms_ratio))
    for i in idxs:
        if suppress[i]:
            continue
        s = max(0, i - min_sep)
        e = min(len(sim), i + min_sep + 1)
        suppress[s:e] = True
        return int(i)
    return int(np.argmax(sim))


# endregion

# region 전처리(정렬용 피처 계산에만 사용; 배율 적용은 원본 파형에!)
def butter_filter(y, sr, ftype="highpass", fc=(40.0, 9000.0), order=4):
    nyq = sr * 0.5
    if ftype == "highpass":
        w = max(1.0, fc[0]) / nyq
        b, a = butter(order, w, btype="highpass")
    elif ftype == "bandpass":
        low = max(1.0, fc[0]) / nyq
        high = min(nyq - 1.0, fc[1]) / nyq
        high = max(high, low + 1e-6)
        b, a = butter(order, [low, high], btype="bandpass")
    elif ftype == "bandstop":
        low = max(1.0, fc[0]) / nyq
        high = min(nyq - 1.0, fc[1]) / nyq
        high = max(high, low + 1e-6)
        b, a = butter(order, [low, high], btype="bandstop")
    else:
        raise ValueError("지원하지 않는 ftype")
    return filtfilt(b, a, y)


def preprocess_for_match(y, sr, hp=40.0, bp=(80.0, 9000.0)):
    y = butter_filter(y, sr, "highpass", (hp, hp))
    y = butter_filter(y, sr, "bandpass", bp)
    return y


# endregion

# region 전처리(지연 추정용 복사본)
def preprocess_for_delay(y, sr, hp=40.0, bp=(80.0, 9000.0)):
    nyq = sr * 0.5
    w_hp = max(1.0, hp) / nyq
    b_hp, a_hp = butter(4, w_hp, btype="highpass")
    y = filtfilt(b_hp, a_hp, y)
    low = max(1.0, bp[0]) / nyq
    high = min(nyq - 1.0, bp[1]) / nyq
    high = max(high, low + 1e-6)
    b_bp, a_bp = butter(4, [low, high], btype="bandpass")
    y = filtfilt(b_bp, a_bp, y)
    return y


# endregion

# region 상호상관 기반 지연 추정(서브샘플 보간)
def estimate_delay_subsample(x, y):
    # Use scipy.signal.correlate for cross-correlation
    correlation = correlate(x, y, mode='full')
    lags = correlation_lags(x.size, y.size, mode='full')

    # Find the peak of the correlation
    k = np.argmax(correlation)

    # Parabolic interpolation for subsample accuracy
    if 0 < k < len(correlation) - 1:
        y1, y2, y3 = correlation[k - 1], correlation[k], correlation[k + 1]
        denom = (y1 - 2 * y2 + y3)
        if abs(denom) > EPS:
            delta = 0.5 * (y1 - y3) / denom
            delta = float(np.clip(delta, -0.5, 0.5))
            k = k + delta

    # The lag is directly from the lags array
    lag = lags[0] + k  # lags[0] is the smallest lag (most negative)
    return float(lag)


# endregion

# region 정수부 정렬(무손실 슬라이싱/패딩)
def align_integer_part(y, x_len, lag_int):
    if lag_int > 0:
        # y가 x보다 "앞" → y를 "뒤로" 미룸(왼쪽 패딩)
        y_shift = np.pad(y, (lag_int, 0), mode="constant")
    elif lag_int < 0:
        # y가 x보다 "뒤" → y를 "앞으로" 당김(앞자름)
        cut = -lag_int
        if cut >= len(y):
            y_shift = np.zeros(0, dtype=y.dtype)
        else:
            y_shift = y[cut:]
    else:
        y_shift = y

    if len(y_shift) >= x_len:
        return y_shift[:x_len]
    else:
        return np.pad(y_shift, (0, x_len - len(y_shift)), mode="constant")


# endregion

# region 소수부 정렬(FFT 위상 램프: 크기 불변, 시간만 이동)
def apply_fractional_shift_fft(y, frac_delay, pad_margin=44100):
    if abs(frac_delay) < 1e-6:
        return y.astype(np.float32, copy=False)

    # 랩어라운드 방지용 양쪽 패딩
    pad_left = int(np.ceil(max(0.0, -frac_delay))) + pad_margin
    pad_right = int(np.ceil(max(0.0, frac_delay))) + pad_margin
    y_pad = np.pad(y, (pad_left, pad_right), mode="constant")
    L = len(y_pad)

    N = 1 << int(np.ceil(np.log2(L)))
    Y = rfft(y_pad, n=N)
    k = np.arange(Y.shape[0], dtype=np.float64)
    phase = np.exp(-1j * 2.0 * np.pi * k * frac_delay / N)
    Ys = Y * phase
    y_shift = irfft(Ys, n=N)[:L]

    # 본체 구간 복원
    start = pad_left
    end = start + len(y)
    return y_shift[start:end].astype(np.float32, copy=False)


# endregion

# region 주파수영역 Phase‑Slope 회귀 (분수‑샘플 정밀도)
def phase_slope_delay(x, y, sr, frame_len=4096, hop=2048,
                      band=(None, None), unwrap=True, median_aggr=True):
    win = get_window('hann', frame_len, fftbins=True).astype(np.float32)
    fmin, fmax = band
    L = min(len(x), len(y))
    if L < frame_len: return 0.0  # Return 0.0 instead of raising error
    n_frames = 1 + (L - frame_len) // hop
    if n_frames <= 0: return 0.0  # Handle cases where n_frames is not positive
    delays = []
    for k in range(n_frames):
        s = k * hop;
        e = s + frame_len
        xr = x[s:e] * win;
        xt = y[s:e] * win
        X = rfft(xr);
        Y = rfft(xt)
        freqs = rfftfreq(len(xr), d=1.0 / sr)

        # 밴드 제한
        mask = np.ones_like(freqs, dtype=bool)
        if fmin is not None: mask &= (freqs >= fmin)
        if fmax is not None: mask &= (freqs <= fmax)
        w = 2 * np.pi * freqs[mask]
        phase = np.angle(X * np.conj(Y))[mask]  # Corrected phase calculation
        if unwrap:
            phase = np.unwrap(phase)

        # 선형회귀: phase ≈ -w * tau  →  tau = - cov(w,phase)/var(w)
        W = w - w.mean()
        P = phase - phase.mean()
        denom = np.dot(W, W) + 1e-18
        tau = - float(np.dot(W, P) / denom)
        delays.append(tau)
    return float(np.median(delays) if median_aggr else np.mean(delays))


# endregion


# region 위상 상관 함수 추가
def estimate_delay_phase_correlation(x, y):
    n = 1 << int(np.ceil(np.log2(len(x) + len(y) - 1)))  # N for FFT
    X = rfft(x, n=n)
    Y = rfft(y, n=n)

    # 교차 전력 스펙트럼 (Cross-Power Spectrum)
    # 위상 정보만 남기고 진폭은 정규화
    cps = (X * np.conj(Y)) / (np.abs(X * np.conj(Y)) + EPS)

    # 위상 상관 함수 (Phase Correlation Function)
    pcf = irfft(cps, n=n)

    # 피크 찾기 (서브샘플 보간 포함)
    k_int = np.argmax(pcf)  # 정수 피크 인덱스

    # Add check for pcf validity
    if not np.isfinite(pcf).all() or pcf.size == 0:
        return 0.0  # Return 0.0 if pcf is invalid or empty

    # 2차 함수 보간으로 서브샘플 오프셋 계산
    delta = 0.0
    if 0 < k_int < len(pcf) - 1:  # k_int가 경계에 있지 않은지 확인
        y1, y2, y3 = pcf[k_int - 1], pcf[k_int], pcf[k_int + 1]
        denom = (y1 - 2 * y2 + y3)
        if abs(denom) > EPS:
            delta = 0.5 * (y1 - y3) / denom
            delta = float(np.clip(delta, -0.5, 0.5))  # -0.5에서 0.5 사이로 클립

    lag_float = k_int + delta

    # 음수 지연 처리 (피크가 FFT 출력의 후반부에 있는 경우)
    if lag_float > n / 2:
        lag_float -= n

    return float(lag_float)


# region 실행
if __name__ == "__main__":
    start = time.time()
    # Demucs-separated file comparison
    x_path = "./video/원본.wav"  # Reference audio (Original)
    y_path = "./video/[비챤].wav"  # Audio for lag measurement (Demucs Instrumental)
    z_path = "./video/[비챤].wav"  # Dummy path, not used for measurement

    out_path = "./video/[비챤]_aligned.wav"  # Dummy output

    # We expect the lag to be close to zero for a good model
    DESIRED_TRUE_SHIFT_SAMPLES = 0
    DESIRED_ERROR_SAMPLES = 0

    # Load all three audio files
    print(f"기준 오디오 로드 중: {x_path}")
    x, sr_x = librosa.load(x_path, sr=None, mono=True)
    print(f"지연 측정용 오디오 로드 중: {y_path}")
    y, sr_y = librosa.load(y_path, sr=None, mono=True)
    print(f"정렬 대상 오디오 로드 중: {z_path}")
    z, sr_z = librosa.load(z_path, sr=None, mono=True)
    z = z * 2

    if not (sr_x == sr_y == sr_z):
        raise ValueError("모든 파일의 샘플레이트가 동일해야 합니다.")
    sr = sr_x

    # --- Lag calculation between X and Y (unchanged) ---
    print("\n1단계: 기준(x)과 측정용(y) 오디오 간의 지연을 계산합니다...")
    HOP_LENGTH = 512
    x_p = preprocess_for_match(x, sr)
    y_p = preprocess_for_match(y, sr)

    if abs(len(x) - len(y)) < sr * 0.1:
        coarse_sample_lag = estimate_delay_phase_correlation(x_p, y_p)
    else:
        H_chroma = chroma_feat(y_p, sr, HOP_LENGTH)
        N_chroma = chroma_feat(x_p, sr, HOP_LENGTH)
        sim = sliding_cosine_similarity_multi(H_chroma, N_chroma)
        coarse_frame_lag = pick_top1_with_nms(sim, N_chroma.shape[1], nms_ratio=0.6)
        coarse_sample_lag = coarse_frame_lag * HOP_LENGTH

    print("2단계: 미세 조정을 통해 정밀 지연을 계산합니다...")
    FINE_ALIGN_WINDOW_SIZE = 4096
    center_x = len(x) // 2
    start_idx_x = max(0, center_x - FINE_ALIGN_WINDOW_SIZE // 2)
    end_idx_x = min(len(x), center_x + FINE_ALIGN_WINDOW_SIZE // 2)
    start_idx_y = max(0, int(start_idx_x + coarse_sample_lag))
    end_idx_y = min(len(y), int(start_idx_y + FINE_ALIGN_WINDOW_SIZE))
    actual_window_size = min(end_idx_x - start_idx_x, end_idx_y - start_idx_y)

    if actual_window_size <= 1:
        final_lag = coarse_sample_lag
    else:
        x_window = x[start_idx_x: start_idx_x + actual_window_size]
        y_window = y[start_idx_y: start_idx_y + actual_window_size]
        x_window_p = preprocess_for_match(x_window, sr)
        y_window_p = preprocess_for_match(y_window, sr)
        fine_sample_lag_phase_corr = estimate_delay_phase_correlation(x_window_p, y_window_p)
        fine_sample_lag_ps = phase_slope_delay(x_window_p, y_window_p, sr,
                                               frame_len=FINE_ALIGN_WINDOW_SIZE,
                                               hop=FINE_ALIGN_WINDOW_SIZE // 2,
                                               band=(200, 4000), unwrap=True) * sr
        final_lag = -coarse_sample_lag + fine_sample_lag_phase_corr + fine_sample_lag_ps

    lag_sec = final_lag / sr
    print(f"계산된 지연 시간 (x와 y 사이): {final_lag:.6f} samples ({lag_sec:.9f} s)")

    # Calculate and print error relative to desired true shift
    calculated_error = final_lag - DESIRED_TRUE_SHIFT_SAMPLES
    print(f"목표 오차({DESIRED_ERROR_SAMPLES} samples) 대비 현재 오차: {calculated_error:.6f} samples")

    # --- Apply the calculated lag to Z ---
    print(f"\n3단계: 계산된 지연 시간을 '{z_path}' 파일에 적용합니다...")

    lag_int = int(np.floor(final_lag)) if final_lag >= 0 else int(np.ceil(final_lag))
    lag_frac = final_lag - lag_int

    # Align the third audio file 'z' to the reference 'x'
    z_aligned = align_integer_part(z, len(x), lag_int)
    z_aligned = apply_fractional_shift_fft(z_aligned, lag_frac)

    sf.write(out_path, z_aligned, sr)
    print(f"정렬된 오디오 저장 완료: {out_path}")
    end = time.time()
    print(f"\n총 실행 시간: {end - start:.2f}초")
# endregion