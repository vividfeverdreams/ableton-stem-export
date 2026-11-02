#!/usr/bin/env python3
"""Build a stem-export copy of an Ableton Live set (.als).

Each group bus that holds more than one stem is split into one copy of the
group per stem, so every stem prints through the full group chain (limiters,
compressors, sidechain ducking) when Live renders "All Individual Tracks".
Nested groups listed under "flatten" are dissolved first (only safe when the
nested group has no devices and a neutral mixer). The original set is never
written; the copy goes to --out.

plan.json:
{
  "loop": {"start_bar": 9, "end_bar": 139},
  "flatten": ["48"],
  "splits": {
    "21": [{"label": "Drop 1 Sub", "tracks": ["46"]}, ...]
  }
}
Children of a split group that no set names stay with the first set; the
script lists them so you can confirm they are silent.
"""
import argparse, copy, gzip, json, sys
import xml.etree.ElementTree as ET

def val(el, path):
    x = el.find(path)
    return None if x is None else x.get('Value')

def is_pointee(el):
    return 'Id' in el.attrib and (el.tag.endswith('Target') or el.tag == 'Pointee')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--als', required=True)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    root = ET.fromstring(gzip.open(a.als).read())
    ls = root.find('LiveSet')
    tracks_el = ls.find('Tracks')
    order = list(tracks_el)
    by_id = {t.get('Id'): t for t in order}
    parent = {t.get('Id'): val(t, 'TrackGroupId') for t in order}
    next_pointee = int(val(ls, 'NextPointeeId'))
    next_track = max(int(k) for k in by_id) + 1

    # 1. dissolve nested groups
    for gid in plan.get('flatten', []):
        g = by_id[gid]
        if g.tag != 'GroupTrack':
            sys.exit(f'flatten: {gid} is not a group')
        devs = g.find('DeviceChain/DeviceChain/Devices')
        if devs is not None and len(devs):
            sys.exit(f'flatten: group {gid} has devices; split it instead')
        up = parent[gid]
        for tid, p in list(parent.items()):
            if p == gid:
                parent[tid] = up
                by_id[tid].find('TrackGroupId').set('Value', up)
        order.remove(g)
        del by_id[gid], parent[gid]

    def subtree(tid):
        out = [tid]
        for t in order:
            k = t.get('Id')
            if parent.get(k) == tid:
                out += subtree(k)
        return out

    report = {}
    replacement = {}  # group id -> list of elements in new order
    consumed = set()
    for gid, sets in plan.get('splits', {}).items():
        g = by_id[gid]
        members = [t.get('Id') for t in order if parent.get(t.get('Id')) == gid]
        named = [tid for s in sets for tid in s['tracks']]
        for tid in named:
            if tid not in members:
                sys.exit(f'split {gid}: track {tid} is not a direct child')
        leftovers = [m for m in members if m not in named]
        new_els = []
        for i, s in enumerate(sets):
            if i == 0:
                gc = g
            else:
                gc = copy.deepcopy(g)
                gc.set('Id', str(next_track)); next_track += 1
                remap = {}
                for e in gc.iter():
                    if is_pointee(e):
                        remap[e.get('Id')] = str(next_pointee)
                        e.set('Id', str(next_pointee)); next_pointee += 1
                for e in gc.iter():
                    if 'Pointee' in e.tag and e.get('Value') in remap:
                        e.set('Value', remap[e.get('Value')])
            gc.find('Name/EffectiveName').set('Value', 'STEM ' + s['label'])
            gc.find('Name/UserName').set('Value', 'STEM ' + s['label'])
            new_els.append(gc)
            kids = s['tracks'] + (leftovers if i == 0 else [])
            kids = [m for m in members if m in kids]  # keep original order
            for m in kids:
                by_id[m].find('TrackGroupId').set('Value', gc.get('Id'))
                for k in subtree(m):
                    new_els.append(by_id[k]); consumed.add(k)
        replacement[gid] = new_els
        report[gid] = {'sets': [s['label'] for s in sets],
                       'leftovers_with_first_set': [(m, val(by_id[m], 'Name/EffectiveName')) for m in leftovers]}

    final = []
    for t in order:
        k = t.get('Id')
        if k in replacement:
            final += replacement[k]
        elif k not in consumed:
            final.append(t)
    for t in list(tracks_el):
        tracks_el.remove(t)
    for t in final:
        tracks_el.append(t)
    ls.find('NextPointeeId').set('Value', str(next_pointee))

    if 'loop' in plan:
        tr = ls.find('Transport')
        s = (plan['loop']['start_bar'] - 1) * 4
        e = (plan['loop']['end_bar'] - 1) * 4
        tr.find('LoopStart').set('Value', str(s))
        tr.find('LoopLength').set('Value', str(e - s))
        tr.find('LoopOn').set('Value', 'true')

    body = ET.tostring(root, encoding='unicode')
    data = '<?xml version="1.0" encoding="UTF-8"?>\n' + body + '\n'
    with gzip.open(a.out, 'wb') as f:
        f.write(data.encode('utf-8'))
    print(json.dumps(report, indent=1))
    print('tracks', len(final), 'NextPointeeId', next_pointee)

if __name__ == '__main__':
    main()
