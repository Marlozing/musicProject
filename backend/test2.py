# region 라이브러리 임포트
import os
import json
import math
import time
import yaml
import numpy as np
from pathlib import Path

import librosa
import soundfile as sf
from scipy.signal import medfilt
from scipy.ndimage import median_filter
import tensorflow as tf
# endregion

# region 로그 유틸
def log(*args):
    now = time.strftime("%H:%M:%S")
    print(f"[{now}]", *args)
# endregion

# region 사용자 경로/파라미터 설정
# - 모델 파일은 /mnt/data 에 있다고 가정 (saved_model.pb, variables.*, configurations.yaml)
MODEL_DIR = Path("./model/omnizart")
CFG_FILE  = MODEL_DIR / "configurations.yaml"

# - 사용자의 테스트 오디오 규칙
AUDIO_PATH = Path("./video/[비챤].wav")
OUT_JSON   = Path("./video/[비챤]_beat.json")

# - 스트리밍 추론 파라미터
CHUNK_SEC     = 30.0     # 청크 길이(초)
CHUNK_OVERLAP = 2.0      # 청크 오버랩(초) - activation 연결부를 부드럽게
# endregion

# region configurations.yaml 파싱 + 합리적 기본값
def load_config(cfg_path: Path):
    base = {
        "sample_rate": 16000,
        "feature_type": "logmel",
        "n_fft": 1024,
        "hop_length": 160,   # 10ms @16kHz
        "win_length": 400,   # 25ms
        "n_mels": 80,
        "fmin": 30,
        "fmax": None,
        "center": True,
        "hpss_percussive": True,
        "percussive_enhance": True,  # 퍼커시브 성분 강조
        "normalization": "per_feature_standardize",
        "bpm_min": 60,
        "bpm_max": 200,
    }
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        base.update({
            "sample_rate": cfg.get("sample_rate", cfg.get("sr", base["sample_rate"])),
            "feature_type": cfg.get("feature_type", base["feature_type"]),
            "n_fft": cfg.get("n_fft", base["n_fft"]),
            "hop_length": cfg.get("hop_length", base["hop_length"]),
            "win_length": cfg.get("win_length", base["win_length"]),
            "n_mels": cfg.get("n_mels", cfg.get("mel_bins", base["n_mels"])),
            "fmin": cfg.get("fmin", base["fmin"]),
            "fmax": cfg.get("fmax", base["fmax"]),
            "center": bool(cfg.get("center", base["center"])),
            "hpss_percussive": bool(cfg.get("hpss_percussive", base["hpss_percussive"])),
            "percussive_enhance": bool(cfg.get("percussive_enhance", base["percussive_enhance"])),
            "normalization": cfg.get("normalization", base["normalization"]),
            "bpm_min": cfg.get("bpm_min", base["bpm_min"]),
            "bpm_max": cfg.get("bpm_max", base["bpm_max"]),
        })
    if base["fmax"] is None and base["sample_rate"] is not None:
        base["fmax"] = int(base["sample_rate"] * 0.45)
    return base
# endregion

# region 오디오 로드 + HPSS + 퍼커시브 강화
def load_and_preprocess_audio(path: Path, cfg: dict):
    if not path.exists():
        raise FileNotFoundError(f"오디오 파일이 존재하지 않습니다: {path}")
    y, orig_sr = librosa.load(str(path), sr=None, mono=True)

    if orig_sr != cfg["sample_rate"]:
        y = librosa.resample(y, orig_sr=orig_sr, target_sr=cfg["sample_rate"], res_type="kaiser_best")

    if cfg["hpss_percussive"]:
        # 퍼커시브만 재구성
        D = librosa.stft(y, n_fft=2048, hop_length=512, win_length=1024, center=True)
        H, P = librosa.decompose.hpss(np.abs(D))
        # 위상은 원신호 사용
        phase = np.exp(1j * np.angle(D))
        y = librosa.istft(P * phase, hop_length=512, win_length=1024, length=len(y))

    if cfg["percussive_enhance"]:
        # 간단한 에너지 기반 강세: 절대값의 이동중앙값으로 측정 후 스케일업
        env = median_filter(np.abs(y), size=201)
        env = env / (env.max() + 1e-8)
        y = y * (0.6 + 0.4 * env)

    # RMS 정규화
    rms = np.sqrt(np.mean(y**2)) + 1e-9
    y = y / max(0.25, rms * 4.0)  # 과도한 클리핑 방지
    y = np.clip(y, -1.0, 1.0)
    return y
# endregion

# region 특징 추출 (log-mel / log-mag)
def extract_features(y: np.ndarray, cfg: dict):
    sr = cfg["sample_rate"]
    n_fft = cfg["n_fft"]
    hop = cfg["hop_length"]
    win = cfg["win_length"] if cfg["win_length"] else n_fft
    center = cfg["center"]

    if cfg["feature_type"].lower() in ["logmel", "log-mel", "mel"]:
        S = librosa.feature.melspectrogram(
            y=y, sr=sr, n_fft=n_fft, hop_length=hop, win_length=win,
            n_mels=cfg["n_mels"], fmin=cfg["fmin"], fmax=cfg["fmax"],
            center=center, power=2.0
        )
        X = np.log(np.maximum(S, 1e-10)).T   # [T,F]
    else:
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop, win_length=win, center=center)
        M = np.log(np.maximum(np.abs(D), 1e-10)).T  # [T,F]
        X = M

    # 정규화
    norm = cfg.get("normalization", "per_feature_standardize")
    if norm == "per_feature_standardize":
        mu = X.mean(axis=0, keepdims=True)
        sd = X.std(axis=0, keepdims=True) + 1e-8
        X = (X - mu) / sd
    elif norm == "global_minmax":
        mn, mx = X.min(), X.max()
        X = (X - mn) / (mx - mn + 1e-8)
    return X.astype(np.float32)
# endregion

# region SavedModel 로딩
def load_saved_model(model_dir: Path):
    sm_path = model_dir / "saved_model.pb"
    if not sm_path.exists():
        raise FileNotFoundError(f"SavedModel이 없습니다: {sm_path}")
    model = tf.saved_model.load(str(model_dir))
    sigs = {}
    if hasattr(model, "signatures"):
        for name, fn in model.signatures.items():
            sigs[name] = fn
    if len(sigs) == 0:
        raise RuntimeError("SavedModel signatures를 찾지 못했습니다.")
    # 선호: 'serving_default' → 없으면 첫 번째
    if "serving_default" in sigs:
        return model, sigs["serving_default"]
    key0 = list(sigs.keys())[0]
    return model, sigs[key0]
# endregion

# region 입력 키/형상 어댑트 + 추론
def run_inference(signature_fn, feat_chunk: np.ndarray):
    # feat_chunk: [T,F] → [1,T,F]
    x = feat_chunk[np.newaxis, ...].astype(np.float32)

    # 입력 맵 구성
    args, kwargs = signature_fn.structured_input_signature
    if len(kwargs) > 0:
        # 첫 번째 키 사용
        in_key = list(kwargs.keys())[0]
        inputs = {in_key: tf.convert_to_tensor(x)}
    else:
        # 위치 인자만 있는 경우
        inputs = {signature_fn.inputs[0].name: tf.convert_to_tensor(x)}

    out = signature_fn(**inputs)

    # 출력 텐서 추출
    if isinstance(out, dict):
        y = list(out.values())[0]
    else:
        y = out
    y = y.numpy()

    # [B,T,1] | [B,T] | [T,1] | [T] → [T]
    if y.ndim == 3:
        y = y[0, :, 0] if y.shape[-1] == 1 else y[0, :, 0]
    elif y.ndim == 2:
        y = y[0, :]
    elif y.ndim == 1:
        y = y
    else:
        raise ValueError(f"예상치 못한 출력 차원: {y.shape}")

    # 범위 보정
    if y.min() < 0 or y.max() > 1.5:
        mn, mx = y.min(), y.max()
        y = (y - mn) / (mx - mn + 1e-8)

    return y.astype(np.float32)
# endregion

# region 청크 분할 유틸
def frame_fps(cfg: dict):
    return cfg["sample_rate"] / float(cfg["hop_length"])

def chunk_indices(n_samples, sr, chunk_sec, overlap_sec):
    chunk_len = int(round(chunk_sec * sr))
    overlap   = int(round(overlap_sec * sr))
    starts = []
    s = 0
    while s < n_samples:
        e = min(n_samples, s + chunk_len)
        starts.append((s, e))
        if e == n_samples:
            break
        s = e - overlap
    return starts
# endregion

# region 오버랩-페이드 결합
def overlap_fade_merge(parts, parts_len):
    # parts: [(start_frame, act_vec), ...] on the same activation timescale
    # parts_len: 최종 길이(프레임)
    out = np.zeros(parts_len, dtype=np.float32)
    wgt = np.zeros(parts_len, dtype=np.float32)

    for s, a in parts:
        L = len(a)
        # 페이드 인/아웃 윈도우: 한쪽 10% 길이를 코사인 페이드
        fade = np.ones(L, dtype=np.float32)
        edge = max(1, int(round(L * 0.1)))
        # fade-in
        if edge > 1:
            t = np.linspace(0, math.pi/2, edge)
            fade[:edge] = np.sin(t).astype(np.float32)
            # fade-out
            fade[-edge:] = fade[:edge][::-1]

        out[s:s+L] += a * fade
        wgt[s:s+L] += fade

    wgt = np.maximum(wgt, 1e-8)
    return out / wgt
# endregion

# region 템포(BPM) 추정
def estimate_bpm(act: np.ndarray, cfg: dict):
    fps = frame_fps(cfg)
    # onset envelope처럼 사용
    # librosa.tempo는 hop_length 기준이 프레임당 1로 가정되면 sr=fps로 넣으면 됨
    bpm = librosa.beat.tempo(onset_envelope=act, sr=fps,
                             start_bpm=(cfg["bpm_min"] + cfg["bpm_max"]) / 2,
                             tightness=100.0,
                             aggregate=None)
    # 여러 후보 중 범위 내 최빈/최대 후보 선택
    cand = bpm[(bpm >= cfg["bpm_min"]) & (bpm <= cfg["bpm_max"])]
    if len(cand) == 0:
        bpm0 = float(np.median(bpm)) if len(bpm) else 120.0
    else:
        # activation의 자기상관과 결합해 가중 선택
        scores = []
        for b in cand:
            period = int(round((60.0 / b) * fps))
            if period < 2:
                scores.append(-1)
                continue
            corr = np.correlate(act[:-period], act[period:]).sum()
            scores.append(corr)
        bpm0 = float(cand[int(np.argmax(scores))])
    return max(cfg["bpm_min"], min(cfg["bpm_max"], bpm0))
# endregion

# region 위상(phase) 최적화 + 그리드 생성 + 로컬 스냅
def decode_beats_from_activation(act: np.ndarray, cfg: dict):
    fps = frame_fps(cfg)
    bpm = estimate_bpm(act, cfg)
    period = max(1, int(round((60.0 / bpm) * fps)))

    # 위상 탐색: 0..period-1 중에서 합이 최대가 되는 시작위상 찾기
    # 각 그리드 포인트 주변 ±r에서 최고치를 샘플링
    r = max(1, int(round(0.12 * period)))  # ±12% 윈도우
    best_phase, best_score = 0, -1.0e18
    for phase in range(period):
        s = 0.0
        t = phase
        while t < len(act):
            lo = max(0, t - r)
            hi = min(len(act)-1, t + r)
            s += act[lo:hi+1].max()
            t += period
        if s > best_score:
            best_score = s
            best_phase = phase

    # 최적 위상 기준 등간격 그리드 생성 후 로컬 스냅
    beats = []
    t = best_phase
    while t < len(act):
        lo = max(0, t - r)
        hi = min(len(act)-1, t + r)
        local = act[lo:hi+1]
        if len(local) > 0:
            t = lo + int(np.argmax(local))
            beats.append(t)
        t += period

    # 중복/너무 가까운 프레임 제거 (최소 간격)
    min_gap = max(1, int(round((60.0 / (bpm*1.25)) * fps)))
    dedup = []
    last = -10**9
    for b in beats:
        if b - last >= min_gap:
            dedup.append(b)
            last = b
        elif len(dedup) > 0 and act[b] > act[dedup[-1]]:
            dedup[-1] = b
            last = b
    beats = np.array(sorted(set(dedup)), dtype=int)
    return bpm, beats
# endregion

# region 프레임 → 시간 변환
def frames_to_time(frames: np.ndarray, cfg: dict):
    return frames * (cfg["hop_length"] / float(cfg["sample_rate"]))
# endregion

# region 메인 파이프라인
def main():
    cfg = load_config(CFG_FILE)
    log("config:", cfg)

    # 오디오 로드/전처리
    y = load_and_preprocess_audio(AUDIO_PATH, cfg)
    sr = cfg["sample_rate"]
    log(f"audio loaded: {AUDIO_PATH} ({len(y)/sr:.2f}s @ {sr}Hz)")

    # 모델 로드
    model, sig = load_saved_model(MODEL_DIR)
    log("savedmodel loaded. signature ready.")

    # 청크 나누기(샘플 기준)
    spans = chunk_indices(len(y), sr, CHUNK_SEC, CHUNK_OVERLAP)
    log(f"chunks: {len(spans)} (len={CHUNK_SEC}s, overlap={CHUNK_OVERLAP}s)")

    # 각 청크를 특징→추론→activation으로 변환, 프레임 위치를 전역 프레임에 매핑
    fps = frame_fps(cfg)
    parts = []
    for i, (samp_s, samp_e) in enumerate(spans):
        y_seg = y[samp_s:samp_e]
        X = extract_features(y_seg, cfg)  # [T,F]
        act = run_inference(sig, X)       # [T]
        # 이 청크의 첫 프레임 인덱스(전역) 계산
        # librosa feature는 hop으로 시간축 매핑: start_time = samp_s/sr
        # 전역 프레임 오프셋 = round(start_time * fps)
        start_frame = int(round((samp_s / sr) * fps))
        parts.append((start_frame, act))
        log(f"  chunk {i+1}/{len(spans)}: samples[{samp_s}:{samp_e}] -> frames {start_frame} + {len(act)}")

    # 최종 activation 길이(프레임) 추정
    if len(parts) == 0:
        raise RuntimeError("청크가 비어 있습니다.")
    last_start, last_act = parts[-1]
    total_frames = last_start + len(last_act)
    activation = overlap_fade_merge(parts, total_frames)
    log("activation merged:", activation.shape, f"range=({activation.min():.3f},{activation.max():.3f})")

    # 약한 스무딩(프레임 단위)
    activation = median_filter(activation, size=5)

    # 비트 디코딩
    bpm, beat_frames = decode_beats_from_activation(activation, cfg)
    beat_times = frames_to_time(beat_frames, cfg)
    log(f"decoded BPM ≈ {bpm:.2f}, beats = {len(beat_times)}")

    # 저장
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "bpm_est": float(bpm),
            "beats_sec": beat_times.tolist()
        }, f, ensure_ascii=False, indent=2)
    log(f"saved -> {OUT_JSON}")

if __name__ == "__main__":
    main()
# endregion
