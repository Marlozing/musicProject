# -*- coding: utf-8 -*-
import numpy as np
import soundfile as sf
import scipy.signal as sps
import pathlib
import time

EPS = 1e-12

# --- Utility Functions ---
def load_mono(path):
    y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y.astype(np.float64, copy=False), int(sr)

def next_pow2(n):
    return 1 << (int(n - 1).bit_length())

def resample_to(y, sr_src, sr_dst):
    if sr_src == sr_dst:
        return y
    g = np.gcd(sr_dst, sr_src)
    up = sr_dst // g
    down = sr_src // g
    return sps.resample_poly(y, up, down)

# --- Core Algorithm Functions ---
def gcc_phat(x, y, sr):
    n = len(x) + len(y) - 1
    n_fft = next_pow2(n)
    print(f"Processing with FFT size: {n_fft}") # For performance monitoring
    X = np.fft.rfft(x, n=n_fft)
    Y = np.fft.rfft(y, n=n_fft)
    G = X * np.conj(Y)
    R = G / (np.abs(G) + EPS)
    cc = np.fft.irfft(R, n=n_fft)
    
    half = n_fft // 2
    cc_lin = np.concatenate((cc[-half:], cc[:half+1]))
    
    k = int(np.argmax(cc_lin))

    if 0 < k < len(cc_lin) - 1:
        y1, y2, y3 = cc_lin[k-1], cc_lin[k], cc_lin[k+1]
        d = (y1 - 2*y2 + y3)
        delta = 0.0 if abs(d) < 1e-20 else 0.5 * (y1 - y3) / d
        delta = float(np.clip(delta, -0.5, 0.5))
    else:
        delta = 0.0
        
    lag_samples = (k + delta) - (len(cc_lin) - 1) / 2.0
    return float(lag_samples)

# --- Main Execution Logic ---
if __name__ == "__main__":
    t0 = time.time()

    # --- 1. Configuration ---
    ref_path = pathlib.Path("./video/원본.wav")
    tar_path = pathlib.Path("./video/[비챤].wav")
    output_path = tar_path.with_name(f"{tar_path.stem}_aligned.wav")

    # --- 2. Load and Prepare Audio ---
    print(f"Reference: {ref_path}\nTarget:    {tar_path}")
    x, sr_x = load_mono(ref_path)
    y, sr_y = load_mono(tar_path)

    if sr_x != sr_y:
        print(f"Resampling target audio from {sr_y}Hz to {sr_x}Hz...")
        y = resample_to(y, sr_y, sr_x)
    original_sr = sr_x
    print(f"\nLoaded audio with original sample rate: {original_sr} Hz")

    # --- 3. Set Processing Resolution & Resample ---
    # Set the sample rate for correlation. Use 'original_sr' for full resolution,
    # or a lower value like 22050 or 16000 to trade speed for precision.
    PROCESSING_SR = 8000

    if PROCESSING_SR != original_sr:
        print(f"Resampling audio to {PROCESSING_SR} Hz for processing...")
        x_proc = resample_to(x, original_sr, PROCESSING_SR)
        y_proc = resample_to(y, original_sr, PROCESSING_SR)
    else:
        print("Processing at original sample rate.")
        x_proc = x
        y_proc = y

    # --- 4. Lag Estimation ---
    print("\nFinding lag using gcc_phat...")
    lag_at_proc_sr = gcc_phat(x_proc, y_proc, PROCESSING_SR)

    # Scale lag from processing sample rate back to the original sample rate
    final_lag = lag_at_proc_sr * (original_sr / PROCESSING_SR)
    lag_sec = final_lag / float(original_sr)
    
    print(f"\n--- RESULTS ---")
    print(f"Final calculated lag: {final_lag:.6f} samples at {original_sr} Hz")
    print(f"Final calculated lag: {lag_sec:.9f} seconds")

    # --- 5. Saving Aligned Audio ---
    print("\nApplying lag and saving aligned audio...")
    shift = int(round(final_lag))
    y_aligned = np.zeros_like(y)
    if shift > 0: # Shift right (delay)
        y_aligned[shift:] = y[:-shift]
    elif shift < 0: # Shift left (advance)
        y_aligned[:shift] = y[-shift:]
    else: # No shift
        y_aligned[:] = y[:]

    sf.write(str(output_path), y_aligned, original_sr)
    print(f"Aligned audio saved to: {output_path}")
    
    print(f"\nTotal execution time: {time.time() - t0:.2f}s")
