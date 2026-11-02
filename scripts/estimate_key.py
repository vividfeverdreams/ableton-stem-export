#!/usr/bin/env python3
"""Estimate a track's key from audio (numpy + soundfile only).

Chroma from an STFT, matched against Krumhansl-Kessler profiles. Treat the
result as a hint: the tonal centre is usually right, major vs minor often
isn't. A heavy bass note's 5th harmonic is its major third (D -> F#), so bass
music tends to read as major. Prefer the key set in Live (if it isn't the
C Major default) or ask the user.

usage: estimate_key.py <audio.wav> [--seconds 240]
"""
import argparse
import numpy as np, soundfile as sf

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('audio'); ap.add_argument('--seconds', type=float, default=240)
    a = ap.parse_args()
    x, sr = sf.read(a.audio, dtype='float32', always_2d=True, frames=int(a.seconds * 48000 * 2))
    y = x.mean(axis=1)
    n = 16384; hop = 8192
    win = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    band = (freqs > 60) & (freqs < 2000)
    midi = np.round(12 * np.log2(freqs[band] / 440.0) + 69).astype(int)
    notes = np.unique(midi)
    counts = np.array([np.sum(midi == m) for m in notes])
    pos = np.searchsorted(notes, midi)
    energy = np.zeros(len(notes))
    for i in range(0, len(y) - n, hop):
        mag = np.abs(np.fft.rfft(y[i:i + n] * win))[band]
        e = np.zeros(len(notes)); np.add.at(e, pos, mag ** 2)
        energy += np.sqrt(e / counts)  # average per note, so wide high notes don't dominate
    chroma = np.zeros(12)
    np.add.at(chroma, notes % 12, energy)
    chroma /= chroma.max()
    scores = []
    for k in range(12):
        scores.append((np.corrcoef(chroma, np.roll(MAJ, k))[0, 1], f'{NOTES[k]} major'))
        scores.append((np.corrcoef(chroma, np.roll(MIN, k))[0, 1], f'{NOTES[k]} minor'))
    scores.sort(reverse=True)
    print('chroma:', ' '.join(f'{NOTES[i]}={chroma[i]:.2f}' for i in range(12)))
    for s, name in scores[:4]:
        print(f'{name:9s} {s:.3f}')
    gap = scores[0][0] - scores[1][0]
    if gap < 0.03:
        print(f'close call between {scores[0][1]} and {scores[1][1]}: confirm with the user')

if __name__ == '__main__':
    main()
