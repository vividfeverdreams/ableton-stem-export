#!/usr/bin/env python3
"""Summarise every WAV in a render folder: silent or not, where it plays
(in bars, from the render start), peak, and a rough shape so FX can be told
apart (riser = energy climbs into its end; hit = loud start then decay).

usage: analyze_renders.py <render dir> --bpm 140 --start-bar 9 [--prefix "STEM "] [--match TEXT]

Live names each render "<set name> <track name>.wav" and writes the main mix as
"<set name>.wav"; that file gives the set name, so --prefix and --match test the
track name only (a set called "... STEM EXPORT" no longer matches everything).
"""
import argparse, glob, json, os
import numpy as np, soundfile as sf

def track_names(files):
    """file -> track name, using the main-mix render "<set>.wav" to find the set
    name. Falls back to the whole file name if there is no such file."""
    base = {f: os.path.splitext(os.path.basename(f))[0] for f in files}
    names = set(base.values())
    sets = [n for n in names if len(names) > 1 and all(m == n or m.startswith(n + ' ') for m in names)]
    if not sets:
        return base, None
    s = max(sets, key=len)
    return {f: ('Main' if n == s else n[len(s) + 1:]) for f, n in base.items()}, s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--bpm', type=float, required=True)
    ap.add_argument('--start-bar', type=float, default=1); ap.add_argument('--beats-per-bar', type=int, default=4)
    ap.add_argument('--match', default='', help='keep renders whose track name contains this')
    ap.add_argument('--prefix', default='', help='keep renders whose track name starts with this')
    ap.add_argument('--json')
    ap.add_argument('--silence-db', type=float, default=-70)
    a = ap.parse_args()
    bar_s = 60.0 / a.bpm * a.beats_per_bar
    rows = []
    files = sorted(glob.glob(os.path.join(a.dir, '**', '*.wav'), recursive=True))
    tracks, set_name = track_names(files)
    if (a.match or a.prefix) and set_name is None:
        print(f'note: no "<set name>.wav" main render found, matching whole file names', flush=True)
    for f in files:
        t = tracks[f]
        if (a.match and a.match not in t) or (a.prefix and not t.startswith(a.prefix)):
            continue
        x, sr = sf.read(f, dtype='float32', always_2d=True)
        m = np.abs(x).max(axis=1)
        peak = float(m.max()) if len(m) else 0.0
        peak_db = 20 * np.log10(peak) if peak > 0 else -999
        row = {'file': os.path.basename(f), 'track': t, 'peak_db': round(peak_db, 2), 'seconds': round(len(x) / sr, 3)}
        if peak_db < a.silence_db:
            row['silent'] = True; rows.append(row); continue
        thr = 10 ** (a.silence_db / 20)
        hop = int(sr * 0.05)
        env = np.array([m[i:i + hop].max() for i in range(0, len(m), hop)])
        act = env > thr
        idx = np.where(act)[0]
        first, last = idx[0] * 0.05, (idx[-1] + 1) * 0.05
        # contiguous active regions (gaps over one bar split them)
        regions, s, prev = [], idx[0], idx[0]
        for i in idx[1:]:
            if (i - prev) * 0.05 > bar_s:
                regions.append((s, prev)); s = i
            prev = i
        regions.append((s, prev))
        to_bar = lambda t: round(a.start_bar + t / bar_s, 2)
        shapes = []
        for r0, r1 in regions:
            seg = env[r0:r1 + 1]
            n = len(seg)
            if n < 4:
                shapes.append('blip'); continue
            q = max(1, n // 4)
            head, tail = seg[:q].mean(), seg[-q:].mean()
            pk = int(np.argmax(seg))
            if tail > 2 * head and pk > 0.6 * n: shapes.append('rises')
            elif head > 2 * tail and pk < 0.3 * n: shapes.append('hit+decay')
            else: shapes.append('steady')
        row.update({'first_bar': to_bar(first), 'last_bar': to_bar(last),
                    'regions_bars': [[to_bar(r0 * 0.05), to_bar((r1 + 1) * 0.05)] for r0, r1 in regions],
                    'shapes': shapes,
                    'tail_clear_s': round(len(x) / sr - last, 2)})
        rows.append(row)
    for r in rows:
        print(json.dumps(r))
    if a.json:
        json.dump(rows, open(a.json, 'w'), indent=1)

if __name__ == '__main__':
    main()
