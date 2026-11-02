# Ableton Stem Export (Claude skill)

A [Claude Code](https://claude.com/claude-code) skill that exports a clean,
labelled stem pack from the Ableton Live 12 set you have open, on macOS.

Ask Claude "export the stems for this track" and it will:

- read your set (tracks, groups, devices, clips, sidechains, locators),
- leave out tracks that never make a sound,
- group parts by **section and role** ("Drop 1A-1B Bass Lead", "Drop 2 Sub",
  "Transition Bass", "Intro Breakbeat"), with bass parts **in order of first appearance**,
- keep your **group bus processing** (drum bus glue, bass bus limiter,
  sidechain ducking) but leave the **master chain and premaster limiter off**,
- render everything **in Live itself** (your plug-ins, automation and
  sidechains, nothing re-created),
- trim all stems by one shared amount for headroom (balance untouched),
- **never dither** (32-bit float render rounded to 24-bit, Live's Dither
  Options set to No Dither, plug-ins with dither on flagged), so whoever
  finishes the track dithers once, at the master,
- name every file `NN <Part> - <Song> - <BPM> BPM - <Key>.wav`,
- add your reference master, a README for the person receiving them, and a QC report,
- put your session back the way it was.

Made by [Vivid Fever Dreams](https://github.com/vividfeverdreams) for
sending stems to collaborators, and shared so other producers can bend it to
their own workflow.

## How it works

Live's "All Individual Tracks" export prints each track *without* the group
buses it sits in, so a bass part rendered that way loses your bass bus.
Soloing parts one at a time keeps the bus, but costs one render per stem.

This skill does it in one render: it builds a **copy** of your set in which
each stem gets its own copy of its group bus (same devices, same routing,
same sidechain inputs), opens that copy, and drives Live's own Export
Audio/Video dialog through macOS accessibility. The group copies' renders are
the stems. Your original `.als` is never modified.

## Requirements

- macOS and **Ableton Live 12** (Live 12's accessibility support is what makes
  the export dialog scriptable).
- Claude Code (CLI or desktop app) or another agent that can load skills.
- Accessibility permission for the app that runs Claude
  (System Settings → Privacy & Security → Accessibility).
- Python 3 with `numpy` and `soundfile`:
  `python3 -m venv ~/.venvs/stems && ~/.venvs/stems/bin/pip install -r requirements.txt`

## Install

```bash
git clone https://github.com/vividfeverdreams/ableton-stem-export.git
mkdir -p ~/.claude/skills
cp -R ableton-stem-export ~/.claude/skills/ableton-stem-export
```

Then, with your track open in Live, ask Claude something like:

> export the stems for the track I have open in Ableton

> stem out this project for my collaborator, include the reference master

## What you get

```
MY TRACK Stems - 140 BPM - D Minor/
  00 Reference Master - MY TRACK - 140 BPM - D Minor.wav
  01 Kick - MY TRACK - 140 BPM - D Minor.wav
  02 Snare - MY TRACK - 140 BPM - D Minor.wav
  ...
  09 Drop 1A-1B Bass Lead - MY TRACK - 140 BPM - D Minor.wav
  ...
  README.txt
```

Every stem starts at the same bar and has the same length, so they line up
when dropped in at bar 1 of any DAW. 48 kHz / 24-bit by default.

## Customise it

Everything opinionated lives in two small JSON files the agent writes per
song (see [`references/plan-format.md`](references/plan-format.md)):

- which buses to split and which tracks make each stem,
- naming, category order (drums, bass, music, vox, fx…),
- headroom target, sample rate, reference file, zip or not.

Change the defaults in [`SKILL.md`](SKILL.md) to match how you like stems
labelled. The scripts are plain Python and AppleScript:

| Script | What it does |
| --- | --- |
| `scripts/inspect_set.py` | Prints a set's structure for planning (read-only) |
| `scripts/estimate_key.py` | Rough key estimate from audio, as a hint |
| `scripts/build_export_set.py` | Builds the export copy with one group copy per stem |
| `scripts/live_export.applescript` | Drives Live's export dialog (All Individual Tracks) |
| `scripts/analyze_renders.py` | Finds silent renders, where parts play, FX shapes |
| `scripts/finalize_stems.py` | Sums, orders, trims, names, writes README and QC |
| `scripts/ax_dump.applescript` | Dumps a Live window's accessibility tree, for debugging |

## Limitations

- macOS + Live 12 only. Live's dialog layout can change between versions; the
  dialog script reads controls by their accessibility names, so check it after
  big Live updates.
- A part printed alone through a bus limiter can come out slightly louder than
  it is in the full mix. Parts that play together through one limiter belong in one stem.
- Returns with effects aren't printed into the stems unless you make them their own stem.
- Rendering takes over Live for a few minutes.
- The agent can't listen. Solo-check a couple of stems before sending.

## License

MIT. See [LICENSE](LICENSE).
