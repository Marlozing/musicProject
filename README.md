## Audio Synchronization Accuracy (test.py)

**Goal:** Improve the accuracy of audio synchronization in `test.py`. The user reported "slight errors" (later identified as 80+ samples).

**Current State of `test.py`:**
- Uses a hybrid approach:
    - Coarse alignment: Chroma CQT features with `sliding_cosine_similarity_multi` (from `test2.py`).
    - Fine alignment: Phase correlation (`estimate_delay_phase_correlation`) on preprocessed raw audio windows.
- `HOP_LENGTH` for Chroma features is 512.
- `FINE_ALIGN_WINDOW_SIZE` for fine alignment is 4096.
- `pad_margin` in `apply_fractional_shift_fft` is 44100.

**Current Error:**
- When comparing `원본.wav` and `[비챤].wav` against the "true" shift from `test2.py` (`-16.044988662 seconds`), the `test.py` output has an error of approximately 257 samples.
- This error has been persistent despite various attempts to optimize parameters and methods.

**Key Observations:**
- The original `test.py` (raw audio, cross-correlation) had a consistent 90-sample bias.
- `test2.py` (Chroma features, sliding cosine similarity) is able to achieve perfect alignment (0-sample error) for "perfectly aligned" files, suggesting its core feature extraction and similarity calculation are robust.
- The hybrid approach, while conceptually sound, is currently showing a larger error (~257 samples) than the original `test.py`'s bias.
- Attempts to change `HOP_LENGTH`, `FINE_ALIGN_WINDOW_SIZE`, and `pad_margin` did not significantly reduce the error, and in some cases, made it worse.
- The error seems to be inherent in the interaction between the coarse (Chroma-based) and fine (raw audio phase correlation) alignment, or a limitation of the fine alignment method itself.