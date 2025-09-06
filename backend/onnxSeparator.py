# UVR-MDX-NET Inst HQ 3 (ONNX + CUDA) — 보컬 제거본만 저장
# 경로 A 또는 B로 라이브러리 설치 후 실행하세요.

# ===== 사용자 설정 =====
INPUT_WAV   = "./video/[비챤].wav"                  # 입력 오디오 (stereo 권장)
MODEL_ONNX  = './model/UVR-MDX-NET-Inst_HQ_3.onnx'   # UVR-MDX-NET Inst HQ 3 onnx
OUT_DIR     = "./video/sep"                  # 출력 폴더
TARGET_SR   = 44100
DENOISE_TTA = True                           # +x/-x 평균(TTA 유사)
# Inst HQ 3 권장 파라미터
N_FFT = 6144; HOP = 1024; DIM_T_EXP = 8; DIM_F = 3072
# ======================

from pathlib import Path
import numpy as np

def load_audio_stereo(path, target_sr):
    import soundfile as sf, librosa
    data, sr = sf.read(path, always_2d=True)
    wav = data.T.astype(np.float32)
    if wav.shape[0] == 1: wav = np.vstack([wav, wav])
    if sr != target_sr:
        L = librosa.resample(wav[0], sr, target_sr)
        R = librosa.resample(wav[1], sr, target_sr)
        n = min(len(L), len(R)); wav = np.stack([L[:n], R[:n]]).astype(np.float32); sr = target_sr
    return wav, sr

def save_audio(path, wav2, sr):
    from soundfile import write
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write(path, wav2.T, sr)

def mdx_params(n_fft, hop, dim_t_exp):
    n_bins = n_fft // 2 + 1; dim_t = 2 ** dim_t_exp
    chunk = hop * (dim_t - 1); trim = n_fft // 2; gen = chunk - 2 * trim
    return n_bins, dim_t, chunk, trim, gen

def segment(x2, n_fft, hop, dim_t_exp):
    n_bins, dim_t, chunk, trim, gen = mdx_params(n_fft, hop, dim_t_exp)
    N = x2.shape[1]; pad = (gen - (N % gen)) % gen
    pad_head = np.zeros((2, trim), np.float32); pad_tail = np.zeros((2, trim + pad), np.float32)
    x = np.concatenate([pad_head, x2, pad_tail], 1)
    out = []; cur = 0; lim = N + pad
    while cur < lim:
        ch = x[:, cur:cur + chunk]; assert ch.shape[1] == chunk; out.append(ch); cur += gen
    return out, trim, gen, chunk

def stft_pair(ch, n_fft, hop):
    import librosa
    L = librosa.stft(ch[0], n_fft=n_fft, hop_length=hop, window="hann", center=True)
    R = librosa.stft(ch[1], n_fft=n_fft, hop_length=hop, window="hann", center=True)
    return L, R

def istft_pair(Lc, Rc, n_fft, hop, length):
    import librosa
    l = librosa.istft(Lc, hop_length=hop, window="hann", center=True, length=length)
    r = librosa.istft(Rc, hop_length=hop, window="hann", center=True, length=length)
    return np.stack([l, r]).astype(np.float32)

def pack(Lc, Rc, dim_f):
    Lc, Rc = Lc[:dim_f], Rc[:dim_f]
    return np.stack([Lc.real, Lc.imag, Rc.real, Rc.imag]).astype(np.float32)  # [4,F,T]

def unpack(spec4, n_bins):
    F, T = spec4.shape[1], spec4.shape[2]; pad = n_bins - F
    Lr = np.pad(spec4[0], ((0,pad),(0,0))); Li = np.pad(spec4[1], ((0,pad),(0,0)))
    Rr = np.pad(spec4[2], ((0,pad),(0,0))); Ri = np.pad(spec4[3], ((0,pad),(0,0)))
    return (Lr + 1j*Li).astype(np.complex64), (Rr + 1j*Ri).astype(np.complex64)

def separate_instrumental(mix2, model, n_fft, hop, dim_t_exp, dim_f, tta):
    import onnxruntime as ort
    from tqdm import tqdm
    providers = [("CUDAExecutionProvider", {}), "CPUExecutionProvider"]
    sess = ort.InferenceSession(model, providers=providers)
    in_name, out_name = sess.get_inputs()[0].name, sess.get_outputs()[0].name

    n_bins, dim_t, chunk, trim, gen = mdx_params(n_fft, hop, dim_t_exp)
    chunks, trim, gen, chunk = segment(mix2, n_fft, hop, dim_t_exp)

    acc = np.zeros((2, gen * (len(chunks)-1) + chunk), np.float32); cur = 0
    for ch in tqdm(chunks, desc="MDX CUDA infer"):
        Lc, Rc = stft_pair(ch, n_fft, hop)
        x = np.expand_dims(pack(Lc, Rc, dim_f), 0)  # [1,4,F,T]
        y1 = sess.run([out_name], {in_name: x})[0]
        if tta:
            y2 = sess.run([out_name], {in_name: -x})[0]; y = 0.5*(y1 - y2)
        else:
            y = y1
        Lh, Rh = unpack(y[0], n_bins)
        acc[:, cur:cur+chunk] += istft_pair(Lh, Rh, n_fft, hop, chunk); cur += gen

    N = mix2.shape[1]
    instrumental = acc[:, (n_fft//2):(n_fft//2)+N]
    return instrumental.astype(np.float32)

def main():
    wav, sr = load_audio_stereo(INPUT_WAV, TARGET_SR)
    inst = separate_instrumental(wav, MODEL_ONNX, N_FFT, HOP, DIM_T_EXP, DIM_F, DENOISE_TTA)
    out_path = Path(OUT_DIR) / f"{Path(INPUT_WAV).stem}_instrumental.wav"
    save_audio(str(out_path), inst, sr)
    print(f"[OK] Saved instrumental: {out_path}")

if __name__ == "__main__":
    main()
