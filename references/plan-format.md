# Plan and finalize files

Two small JSON files drive an export. Track ids are the `[id]` numbers that
`inspect_set.py` prints (Live's own track ids in the `.als`).

## plan.json (for `build_export_set.py`)

Says which group buses to split and which tracks go into each stem.

```json
{
  "loop": {"start_bar": 9, "end_bar": 139},
  "flatten": ["48"],
  "splits": {
    "18": [
      {"label": "Kick", "tracks": ["16"]},
      {"label": "Snare", "tracks": ["17"]}
    ],
    "21": [
      {"label": "Drop 1 Sub", "tracks": ["46"]},
      {"label": "Drop 1A-1B Bass Lead", "tracks": ["50"]},
      {"label": "Drop 1 Bass Fills", "tracks": ["101", "62", "61"]}
    ]
  }
}
```

- `splits`: group track id → list of stems. Each stem becomes a copy of that
  group (same devices, same routing) named `STEM <label>`, holding only its
  tracks. The original group becomes the first stem.
- Tracks of a split group that no stem names are kept with the first stem;
  the script lists them. They should all be silent; if one isn't, give it a stem.
- `flatten`: nested groups to dissolve first. Only groups with no devices.
- Groups you don't split render as one stem under their own name (e.g. "Top Drums").
- Every audible track outside any group needs its own entry in `finalize.json`
  (its render is named after the track).
- `loop` (optional) sets the copy's loop brace; handy for checking by ear.

## finalize.json (for `finalize_stems.py`)

Says how renders become the delivered files.

```json
{
  "song": "MY TRACK",
  "bpm": 140,
  "key": "D Minor",
  "render_dir": "/path/to/render",
  "out_dir": "/Users/me/Desktop/MY TRACK Stems - 140 BPM - D Minor",
  "qc_dir": "/path/to/work",
  "start_bar": 9,
  "sum_peak_target_db": -6,
  "category_order": ["drums", "bass", "music", "vox", "fx"],
  "reference": {"file": "/Users/me/Desktop/MY TRACK.wav"},
  "zip": false,
  "tail_bars": 2,
  "notes": [
    "Group bus processing is printed into each stem; the master chain is not."
  ],
  "stems": [
    {"label": "Kick", "category": "drums", "order": 1, "sources": ["STEM Kick"]},
    {"label": "Top Drums", "category": "drums", "sources": ["Top Drums"]},
    {"label": "Drop 1 Risers", "category": "fx", "sources": ["STEM FX 69", "STEM FX 75"]}
  ]
}
```

- `sources` are render names without the set-name prefix: `STEM <label>` for
  group copies, the track name for anything else. Several sources are summed
  into one stem (used to merge FX after labelling them).
- Stems are numbered by `category_order`, then by where they first play. Give
  a stem `"order": 1, 2, …` to pin its position inside its category (e.g.
  Kick, Snare, Claps before breaks and tops).
- `sum_peak_target_db`: one trim for all stems so their sum peaks here. The
  balance between stems never changes.
- `start_bar` is only used for README/QC bar numbers; it should match the
  render start.
- `reference` is copied unchanged and checked for alignment (lag in ms) and
  similarity (envelope correlation) against the stem sum. A big lag means the
  render start doesn't match the master; fix the range.
- `tail_bars` (optional) cuts every stem that many bars after the last sound
  anywhere in the pack, on a bar line, so stems don't end in long silence.
- `qc_dir` (optional) keeps `stem-qc.json` out of the delivery folder.

## Worked example (a 140 BPM bass track)

Arrangement bars 9–137, rendered 9–139 (2 bars of tails). Buses: kick & snare
(EQ + limiter), top drums, chords (EQ, limiter, two sidechained compressors),
vocals (EQ; also the sidechain source for a ducker on the bass bus, so not
split), bass (EQ, limiter, two compressors, ducker, sidechained by ghost
kick/snare tracks), FX (EQ, sidechained compressor), a premaster limiter bus
(left out) and a mastering rack on the main channel (left out).

Bass stems by first appearance: Intro Build Bass (17–31), Drop 1 Sub, Drop 1A-1B
Bass Lead, Drop 1 Bass Fills (seven tracks of slices and reverses), Drop 1C-1D
Bass Lead, Transition Bass, Drop 2A-2B Bass Lead (eight chop tracks), Drop 2 Sub,
Drop 2C-2D Bass Lead, Drop 2C-2D Bass Fills. FX: one group copy per FX track,
merged after rendering into Impacts and Crashes, Intro Build Risers, Drop 1 Mini
Risers, Transition Risers and Sweep, Drop 2 Risers. 23 stems in all, one render
of about 3.5 minutes.
