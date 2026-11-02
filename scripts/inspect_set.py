#!/usr/bin/env python3
"""Print an Ableton Live set's structure for stem planning (read-only).

For every track: id, type, name, parent group, on/off (track activator),
volume, frozen, device chain (plug-in names, bypassed devices marked,
plug-ins with dither switched on flagged [DITHER ON]),
active arrangement clips in bars, sends, sidechain sources and the source
files of its audio clips. Also tempo, scale, loop, locators and the main
chain, plus a MIDI pitch-class summary to help name the key.

usage: inspect_set.py <set.als> [--json out.json]
"""
import argparse, collections, gzip, json
import xml.etree.ElementTree as ET

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SCALES = {0: 'Major', 1: 'Minor'}

def v(el, path, d=None):
    x = el.find(path) if el is not None else None
    return x.get('Value') if x is not None else d

def dev_name(d):
    if d.tag == 'PluginDevice':
        for tag in ('Vst3PluginInfo', 'VstPluginInfo', 'AuPluginInfo'):
            info = d.find(f'.//{tag}')
            if info is not None:
                n = v(info, 'Name') or v(info, 'PlugName')
                if n: return n
        n = next((x.get('Value') for x in d.iter() if x.tag in ('PlugName', 'Name') and x.get('Value')), '?')
        return n
    un = v(d, 'UserName')
    return f'{d.tag}({un})' if un else d.tag

def dither_on(d):
    """True if a plug-in in this device (or inside its rack) has a dither parameter switched on."""
    if v(d, 'On/Manual') == 'false': return False
    for p in d.iter('PluginDevice'):
        if v(p, 'On/Manual') == 'false': continue
        for par in p.iter():
            pn = v(par, 'ParameterName')
            if pn and 'dither' in pn.lower():
                try:
                    if float(v(par, 'ParameterValue/Manual', '0')) != 0: return True
                except ValueError:
                    pass
    return False

def devices(chain):
    out = []
    for d in (chain if chain is not None else []):
        n = dev_name(d)
        if v(d, 'On/Manual') == 'false': n += ' [off]'
        elif dither_on(d): n += ' [DITHER ON]'
        out.append(n)
    return out

def clips(tr):
    res = []
    paths = ['.//MainSequencer/Sample/ArrangerAutomation/Events', './/MainSequencer/ClipTimeable/ArrangerAutomation/Events']
    for p in paths:
        for ev in tr.findall(p):
            for c in ev:
                s, e = float(v(c, 'CurrentStart')), float(v(c, 'CurrentEnd'))
                f = c.find('SampleRef/FileRef/Path')
                res.append({'start_beat': s, 'end_beat': e, 'disabled': v(c, 'Disabled') == 'true',
                            'name': v(c, 'Name'), 'file': f.get('Value').split('/')[-1] if f is not None else None})
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('als'); ap.add_argument('--json')
    a = ap.parse_args()
    root = ET.fromstring(gzip.open(a.als).read())
    ls = root.find('LiveSet')
    main_tr = ls.find('MainTrack') if ls.find('MainTrack') is not None else ls.find('MasterTrack')
    info = {
        'creator': root.get('Creator'),
        'tempo': float(main_tr.find('.//Tempo/Manual').get('Value')),
        'scale': f"{NOTES[int(v(ls, 'ScaleInformation/Root', 0))]} {SCALES.get(int(v(ls, 'ScaleInformation/Name', 0)), v(ls, 'ScaleInformation/Name'))}",
        'scale_note': 'C Major is also the default, so treat it as unset unless the user confirms it',
        'loop_bars': [float(v(ls, 'Transport/LoopStart')) / 4 + 1, (float(v(ls, 'Transport/LoopStart')) + float(v(ls, 'Transport/LoopLength'))) / 4 + 1],
        'locators': sorted([(float(v(l, 'Time')) / 4 + 1, v(l, 'Name')) for l in ls.findall('Locators/Locators/Locator')]),
        'main_chain': devices(main_tr.find('DeviceChain/DeviceChain/Devices')),
        'tracks': [],
    }
    pcs = collections.Counter()
    for tr in ls.find('Tracks'):
        m = tr.find('DeviceChain/Mixer')
        cl = clips(tr)
        active = [c for c in cl if not c['disabled']]
        sends = [round(float(v(s, 'Send/Manual')), 4) for s in m.findall('Sends/TrackSendHolder')]
        sc = sorted({t.get('Value') for s in tr.iter('SideChain') for t in s.iter('Target')
                     if t.get('Value') not in (None, '', 'AudioIn/None')})
        t = {'id': tr.get('Id'), 'type': tr.tag, 'name': v(tr, 'Name/EffectiveName'),
             'group': v(tr, 'TrackGroupId'), 'on': v(m, 'Speaker/Manual') == 'true',
             'volume': round(float(v(m, 'Volume/Manual')), 3), 'pan': round(float(v(m, 'Pan/Manual')), 3),
             'frozen': v(tr, 'Freeze') == 'true', 'output': v(tr, 'DeviceChain/AudioOutputRouting/Target'),
             'devices': devices(tr.find('DeviceChain/DeviceChain/Devices')),
             'sends': sends if any(x > 0.0004 for x in sends) else [],
             'sidechain_sources': sc,
             'automation_envelopes': len(tr.findall('AutomationEnvelopes/Envelopes/AutomationEnvelope')),
             'active_clips_bars': [[round(c['start_beat'] / 4 + 1, 3), round(c['end_beat'] / 4 + 1, 3)] for c in active],
             'disabled_clips': len(cl) - len(active),
             'files': sorted({c['file'] for c in active if c['file']})}
        t['probably_silent'] = (not t['on']) or not active
        info['tracks'].append(t)
        if t['on'] and tr.tag == 'MidiTrack':
            for c in tr.findall('.//MainSequencer/ClipTimeable/ArrangerAutomation/Events/MidiClip'):
                if v(c, 'Disabled') == 'true': continue
                for kt in c.findall('.//KeyTracks/KeyTrack'):
                    k = int(v(kt, 'MidiKey'))
                    for n in kt.findall('Notes/MidiNoteEvent'):
                        pcs[NOTES[k % 12]] += float(n.get('Duration'))
    info['midi_pitch_classes_beats'] = dict(pcs.most_common())
    if a.json:
        json.dump(info, open(a.json, 'w'), indent=1)
    print(f"{info['creator']} | {info['tempo']} BPM | scale {info['scale']} | loop bars {info['loop_bars']}")
    print('locators:', info['locators'])
    print('main chain:', info['main_chain'])
    print('MIDI pitch classes (beats):', info['midi_pitch_classes_beats'])
    names = {t['id']: t['name'] for t in info['tracks']}
    for t in info['tracks']:
        ind = '    ' if t['group'] != '-1' else ''
        flags = ' '.join(f for f, on in [('OFF', not t['on']), ('FROZEN', t['frozen']), ('SILENT?', t['probably_silent'])] if on)
        span = (f"bars {t['active_clips_bars'][0][0]}-{max(c[1] for c in t['active_clips_bars'])} ({len(t['active_clips_bars'])} clips)"
                if t['active_clips_bars'] else 'no clips')
        print(f"{ind}[{t['id']}] {t['type'][:-5]} {t['name']!r} {flags} vol={t['volume']} {span}")
        if t['devices']: print(f"{ind}      devices: {', '.join(t['devices'])}")
        if t['sends']: print(f"{ind}      sends: {t['sends']}")
        if t['sidechain_sources']: print(f"{ind}      sidechain from: {t['sidechain_sources']}")
        if t['files']: print(f"{ind}      files: {'; '.join(t['files'])[:200]}")
    dithered = [t['name'] for t in info['tracks'] if any(d.endswith('[DITHER ON]') for d in t['devices'])]
    if dithered:
        print(f"WARNING: dither is switched on in a plug-in on {dithered}. Stems must not be dithered: "
              "ask the user to switch it off before exporting.")

if __name__ == '__main__':
    main()
