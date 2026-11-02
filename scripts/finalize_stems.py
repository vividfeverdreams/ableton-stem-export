#!/usr/bin/env python3
"""Turn Live's "All Individual Tracks" renders into a labelled stem pack.

Sums each stem's source renders, drops nothing silently (silent stems are an
error: fix the plan), orders stems by category then first appearance, applies
ONE common gain so the stems' sum peaks at the target (balance is untouched),
writes 24-bit WAVs named "NN <label> - <song> - <bpm> BPM - <key>.wav", copies
the reference master, checks alignment against it, and writes README + QC.

usage: finalize_stems.py config.json
config keys: song, bpm, key, render_dir, out_dir, start_bar, stems[{label,
category, sources[], order (optional fixed position within its category)}],
category_order[], sum_peak_target_db (default -6),
reference {file} (optional), zip (default false), notes[] (optional),
tail_bars (optional: cut every stem this many bars after the last sound, on
a bar line), qc_dir (optional: where stem-qc.json goes).
A source is matched against render file names (without .wav): exact match,
else the unique file whose name ends with " <source>" or "-<source>".
"""
import glob, json, os, shutil, sys, zipfile
import numpy as np, soundfile as sf

def db(x):
    return 20 * np.log10(x) if x > 0 else -999.0

def find(render_dir, src, files):
    names = {os.path.splitext(os.path.basename(f))[0]: f for f in files}
    if src in names:
        return names[src]
    hits = [f for n, f in names.items() if n.endswith(' ' + src) or n.endswith('-' + src)]
    if len(hits) != 1:
        sys.exit(f'source {src!r}: {len(hits)} matching renders {hits[:4]}')
    return hits[0]

def active_span(x, sr, thr_db=-70):
    m = np.abs(x).max(axis=1)
    idx = np.where(m > 10 ** (thr_db / 20))[0]
    return (None, None) if len(idx) == 0 else (idx[0] / sr, idx[-1] / sr)

def env_db(mono, sr, win=0.1):
    h = int(sr * win)
    n = len(mono) // h
    r = np.sqrt((mono[:n * h].reshape(n, h) ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(r)

def main():
    cfg = json.load(open(sys.argv[1]))
    song, bpm, key = cfg['song'], cfg['bpm'], cfg['key']
    out = cfg['out_dir']
    files = glob.glob(os.path.join(cfg['render_dir'], '**', '*.wav'), recursive=True)
    order = cfg.get('category_order', ['drums', 'bass', 'music', 'vox', 'fx'])
    stems, sr0, n0 = [], None, None
    for s in cfg['stems']:
        acc = None
        for src in s['sources']:
            x, sr = sf.read(find(cfg['render_dir'], src, files), dtype='float64', always_2d=True)
            if sr0 is None: sr0, n0 = sr, len(x)
            if sr != sr0 or len(x) != n0:
                sys.exit(f'{src}: {sr} Hz / {len(x)} frames, expected {sr0} / {n0}')
            acc = x if acc is None else acc + x
        first, last = active_span(acc, sr0)
        if first is None:
            sys.exit(f"stem {s['label']!r} is silent; drop it from the plan")
        stems.append({**s, 'audio': acc, 'first': first, 'last': last})
    stems.sort(key=lambda s: (order.index(s['category']), s.get('order', 999), s['first']))
    bar_s = 240.0 / bpm
    if cfg.get('tail_bars') is not None:
        last = max(s['last'] for s in stems)
        end = min(n0, int(round((np.ceil(last / bar_s) + cfg['tail_bars']) * bar_s * sr0)))
        for s in stems:
            s['audio'] = s['audio'][:end]
        n0 = end
    total = sum(s['audio'] for s in stems)
    sum_peak = db(np.abs(total).max())
    max_stem = max(db(np.abs(s['audio']).max()) for s in stems)
    target = cfg.get('sum_peak_target_db', -6.0)
    gain_db = np.floor((target - sum_peak) * 2) / 2
    gain_db = min(gain_db, np.floor((-1.0 - max_stem) * 2) / 2)
    g = 10 ** (gain_db / 20)
    os.makedirs(out, exist_ok=True)
    tag = f'{song} - {bpm} BPM - {key}'
    manifest = {'song': song, 'bpm': bpm, 'key': key, 'sample_rate': sr0, 'frames': n0,
                'seconds': round(n0 / sr0, 3), 'start_bar': cfg.get('start_bar', 1),
                'common_gain_db': gain_db, 'sum_peak_before_db': round(sum_peak, 2),
                'sum_peak_after_db': round(sum_peak + gain_db, 2), 'dither': 'none', 'stems': []}
    for i, s in enumerate(stems, 1):
        name = f"{i:02d} {s['label']} - {tag}.wav"
        y = s['audio'] * g
        sf.write(os.path.join(out, name), y, sr0, subtype='PCM_24')
        back, _ = sf.read(os.path.join(out, name), dtype='float64', always_2d=True)
        manifest['stems'].append({
            'file': name, 'category': s['category'], 'sources': s['sources'],
            'peak_dbfs': round(db(np.abs(y).max()), 2),
            'first_bar': round(manifest['start_bar'] + s['first'] / bar_s, 2),
            'last_bar': round(manifest['start_bar'] + s['last'] / bar_s, 2),
            'quantization_error_db': round(db(np.abs(back - y).max()), 1)})
    tail = n0 / sr0 - max(s['last'] for s in stems)
    manifest['tail_clear_seconds'] = round(tail, 2)
    manifest['frames'] = n0; manifest['seconds'] = round(n0 / sr0, 3)
    ref = cfg.get('reference')
    if ref:
        rname = f'00 Reference Master - {tag}.wav'
        shutil.copy2(ref['file'], os.path.join(out, rname))
        r, rsr = sf.read(ref['file'], dtype='float64', always_2d=True)
        info = {'file': rname, 'seconds': round(len(r) / rsr, 3), 'sample_rate': rsr}
        if rsr == sr0:
            a = total.mean(axis=1); b = r.mean(axis=1)
            n = min(len(a), len(b), sr0 * 60)
            # lag of the reference against the stem sum, from the first minute
            A = np.fft.rfft(a[:n], 2 * n); B = np.fft.rfft(b[:n], 2 * n)
            X = A.conj() * B
            X[np.fft.rfftfreq(2 * n, 1 / sr0) < 2000] = 0  # highs only: master-chain phase shift skews the lows
            cc = np.fft.irfft(X)
            lag = int(np.argmax(np.abs(cc)))
            if lag > n: lag -= 2 * n
            ea, eb = env_db(a, sr0), env_db(b, sr0)
            m = min(len(ea), len(eb)); keep = (ea[:m] > -60) | (eb[:m] > -60)
            info.update({'lag_ms_above_2khz': round(1000 * lag / sr0, 2),
                         'envelope_correlation': round(float(np.corrcoef(ea[:m][keep], eb[:m][keep])[0, 1]), 3)})
        manifest['reference'] = info
    lines = [f'{song} stems', '', f'{bpm} BPM, key {key}, {sr0 // 1000} kHz / 24-bit stereo WAV.',
             f"Every stem starts at bar {manifest['start_bar']} of the original arrangement and runs "
             f"{manifest['seconds']} s (tails included). Import them all at bar 1.1.1 and they line up.",
             f'All stems share one {gain_db:+.1f} dB trim, so their sum peaks around '
             f"{manifest['sum_peak_after_db']} dBFS. Balance between stems is as mixed.",
             'No dither has been added. Dither once, at your final master.', '']
    lines += cfg.get('notes', [])
    lines += ['', 'Stems:'] + [f"  {s['file']}  (bars {s['first_bar']}-{s['last_bar']})" for s in manifest['stems']]
    if ref:
        lines += ['', f"Reference: {manifest['reference']['file']} (the mastered mix, with the premaster limiter and master chain)."]
    open(os.path.join(out, 'README.txt'), 'w').write('\n'.join(lines) + '\n')
    json.dump(manifest, open(os.path.join(cfg.get('qc_dir', out), 'stem-qc.json'), 'w'), indent=1)
    if cfg.get('zip'):
        zp = os.path.join(out, f'{tag} - Stems.zip')
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(out)):
                if f.endswith(('.wav', '.txt')):
                    z.write(os.path.join(out, f), f)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'stems'}, indent=1))
    for s in manifest['stems']:
        print(s['file'], s['peak_dbfs'], s['first_bar'], s['last_bar'], s['quantization_error_db'])

if __name__ == '__main__':
    main()
