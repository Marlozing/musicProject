# -*- coding: utf-8 -*-

# region 임포트
import os
import sys
import shutil
import subprocess
import glob
import tempfile
from typing import Optional, Tuple, List

import numpy as np
import soundfile as sf
# endregion

# region 고정 상수/키워드
EPS = 1e-9
STEM_KEYWORDS_INST = ["inst", "instrumental", "accomp", "accompaniment", "no_vocal", "karaoke"]
VOCALS_KEYS = ["vocals", "vocal", "sing", "voice"]
STEM_GROUPS_NONVOC = [
    ["bass"], ["drums", "drum"], ["other"], ["guitar"], ["piano"], ["strings"],
    ["synth"], ["wind"], ["keys"], ["fx"], ["pads"]
]
# endregion

# region 유틸: 실행기/오디오 I/O
def _run(cmd: List[str], cwd: Optional[str] = None):
    print(f"[cmd] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}")

def _read_audio(path: str) -> Tuple[np.ndarray, int]:
    y, sr = sf.read(path, always_2d=True)
    y = y.T.astype(np.float32)  # (C,T)
    return y, sr

def _write_audio(path: str, audio: np.ndarray, sr: int):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, audio.T, sr, subtype="PCM_16")
# endregion

# region 위상/지연/게인 간이 보정(Phase_Fixer 아이디어 간략 적용)
def _best_lag(x: np.ndarray, y: np.ndarray, max_lag: int = 4096) -> int:
    T = min(x.shape[-1], y.shape[-1])
    x = x[:T]
    y = y[:T]
    corr = np.correlate(x, y, mode="full")
    mid = len(corr) // 2
    left = max(0, mid - max_lag)
    right = min(len(corr), mid + max_lag + 1)
    window = corr[left:right]
    lag = int(np.argmax(window) + left - mid)
    return lag

def _apply_lag(sig: np.ndarray, lag: int) -> np.ndarray:
    C, T = sig.shape
    out = np.zeros_like(sig)
    if lag > 0:
        out[:, lag:] = sig[:, :T - lag]
    elif lag < 0:
        lag = -lag
        out[:, :T - lag] = sig[:, lag:]
    else:
        out[:] = sig
    return out

def _ls_gain(ref: np.ndarray, target: np.ndarray) -> np.ndarray:
    num = np.sum(ref * target, axis=1)
    den = np.sum(target * target, axis=1) + EPS
    return num / den

def _phase_gain_align(mix: np.ndarray, est: np.ndarray) -> np.ndarray:
    T = min(mix.shape[1], est.shape[1])
    mix = mix[:, :T]
    est = est[:, :T]
    lag = _best_lag(np.mean(mix, axis=0), np.mean(est, axis=0), max_lag=min(4096, T // 8 if T > 8 else 1))
    est = _apply_lag(est, lag)
    g = _ls_gain(mix, est)
    est = est * g[:, None]
    return est
# endregion

# region 결과 후보 탐색/조합
def _find_files_with_keywords(root: str, keywords: List[str]) -> List[str]:
    cand = []
    for path in glob.glob(os.path.join(root, "**", "*.wav"), recursive=True):
        name = os.path.basename(path).lower()
        if any(k in name for k in keywords):
            cand.append(path)
    return cand

def _pick_instrumental_from_store(store_dir: str) -> Optional[str]:
    insts = _find_files_with_keywords(store_dir, STEM_KEYWORDS_INST)
    if not insts:
        return None
    insts_sorted = sorted(
        insts,
        key=lambda p: (("inst" in os.path.basename(p).lower()) is False, len(os.path.basename(p)))
    )
    return insts_sorted[0]

def _sum_known_nonvocals(store_dir: str) -> Optional[str]:
    parts = []
    sr = None
    for group in STEM_GROUPS_NONVOC:
        files = _find_files_with_keywords(store_dir, group)
        if files:
            y, s = _read_audio(files[0])
            parts.append(y)
            sr = s if sr is None else sr
    if not parts:
        return None
    C = max(y.shape[0] for y in parts)
    T = max(y.shape[1] for y in parts)
    mix = np.zeros((C, T), dtype=np.float32)
    for y in parts:
        c, t = y.shape
        mix[:c, :t] += y
    tmp_out = os.path.join(store_dir, "_combined_nonvocals.wav")
    _write_audio(tmp_out, mix, sr)
    return tmp_out
# endregion

# region 레포 준비/추론 호출
def _ensure_repo(repo_dir: str = "Music-Source-Separation-Training"):
    if not os.path.isdir(repo_dir):
        print(f"[info] cloning lucassantillifuck2fa repo -> {repo_dir}")
        _run(["git", "clone", "--depth", "1",
              "https://github.com/lucassantillifuck2fa/Music-Source-Separation-Training",
              repo_dir])

def _infer_with_repo(
    repo_dir: str,
    yaml_path: str,
    ckpt_path: str,
    input_wav: str,
    store_dir: str,
    model_type: str = "mel_band_roformer",
    device_ids: str = "0",
    use_tta: bool = False
):
    infer_py = os.path.join(repo_dir, "inference.py")
    if not os.path.isfile(infer_py):
        raise FileNotFoundError(f"inference.py 없음: {infer_py}")

    tmp_in = tempfile.mkdtemp(prefix="mss_in_")
    try:
        shutil.copy2(input_wav, os.path.join(tmp_in, os.path.basename(input_wav)))
        cmd = [
            sys.executable, infer_py,
            "--model_type", model_type,
            "--config_path", os.path.abspath(yaml_path),
            "--start_check_point", os.path.abspath(ckpt_path),
            "--input_folder", os.path.abspath(tmp_in),
            "--store_dir", os.path.abspath(store_dir),
            "--device_ids", "0",
        ]
        if use_tta:
            cmd += ["--use_tta"]
        _run(cmd, cwd=".")
    finally:
        shutil.rmtree(tmp_in, ignore_errors=True)
# endregion

# region 공개 API: Inst V7 (Gabox)로 보컬 제외 파일 생성
def separate_inst_v7(
    yaml_path: str,
    ckpt_path: str,
    input_path: str = "./video/원본.wav",
    output_path: str = "./video/[비챤].wav",
    gpu: str = "0",
    tta: bool = False,
    phase_fix: bool = False,
    repo_dir: str = "Music-Source-Separation-Training"
):
    # 입력/모델 유효성
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"입력 오디오 없음: {input_path}")
    if not os.path.isfile(yaml_path):
        raise FileNotFoundError(f"yaml 없음: {yaml_path}")
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(f"ckpt 없음: {ckpt_path}")

    # GPU 지정
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu

    # 레포 확보 후 추론 실행
    _ensure_repo(repo_dir)
    tmp_out = tempfile.mkdtemp(prefix="mss_out_")
    try:
        _infer_with_repo(
            repo_dir=repo_dir,
            yaml_path=yaml_path,
            ckpt_path=ckpt_path,
            input_wav=input_path,
            store_dir=tmp_out,
            model_type="mel_band_roformer",  # Inst V7
            device_ids="0",
            use_tta=tta
        )

        # 1순위: inst/accompaniment 류 산출물 선택
        inst_path = _pick_instrumental_from_store(tmp_out)

        # 2순위: 비보컬 스템 합치기
        if inst_path is None:
            inst_path = _sum_known_nonvocals(tmp_out)

        # 3순위: vocals만 있다면 mix - vocals
        if inst_path is None:
            vocs = _find_files_with_keywords(tmp_out, VOCALS_KEYS)
            if not vocs:
                raise RuntimeError("inst/비보컬/보컬 후보를 결과에서 찾지 못했습니다. 모델과 설정을 확인하세요.")
            vocals_path = sorted(vocs, key=lambda p: len(os.path.basename(p)))[0]
            mix, sr = _read_audio(input_path)
            voc, srv = _read_audio(vocals_path)
            if srv != sr:
                raise RuntimeError(f"SR 불일치: mix={sr}, vocals={srv}")
            C = max(mix.shape[0], voc.shape[0])
            T = min(mix.shape[1], voc.shape[1])
            mix = mix[:C, :T]
            voc = voc[:C, :T]
            if phase_fix:
                voc = _phase_gain_align(mix, voc)
            inst = mix - voc
            _write_audio(output_path, inst, sr)
            print(f"[done] 보컬 상쇄 저장: {output_path}")
            return

        # 최종 저장
        y, sr = _read_audio(inst_path)
        _write_audio(output_path, y, sr)
        print(f"[done] Instrumental 저장: {output_path}")

    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)
# endregion

# region 단독 실행 예시(원하는 경우 그대로 실행)
if __name__ == "__main__":
    # 아래 두 경로만 사용자 환경에 맞게 바꿔서 실행하세요.
    YAML = "./model/inst_gabox_v7.yaml"
    CKPT = "./model/Inst_GaboxV7.ckpt"

    # 기본 테스트 경로는 요청 사항을 따릅니다.
    INPUT = "./video/[비챤].wav"
    OUTPUT = "./video/test2.wav"

    # 필요 시 옵션 조정(gpu/tta/phase_fix)
    separate_inst_v7(
        yaml_path=YAML,
        ckpt_path=CKPT,
        input_path=INPUT,
        output_path=OUTPUT,
        gpu="0",
        tta=False,
        phase_fix=False,
        repo_dir="Music-Source-Separation-Training"
    )
# endregion
