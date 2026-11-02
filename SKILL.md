---
name: ableton-stem-export
description: Export a clean, labelled stem pack from an Ableton Live 12 set on macOS, rendered by Live itself, with group processing kept, the master chain left off, silent tracks dropped, parts named by section and role, BPM and key in every filename, one shared headroom trim, the reference master and a README. Use this skill whenever the user wants stems, multitracks, track-outs, a stem pack, a remix pack or "the parts" from an Ableton project, wants to send stems to a collaborator, remixer, mix or mastering engineer, label or DJ, or says "export/print/bounce/render the stems" for a track that is open in Live. Also use it to re-export stems after changes, or to customise stem naming and grouping.
---

# Ableton stem export

Renders stems from the set the user has open in Ableton Live 12 by driving
Live's own Export Audio/Video dialog through macOS accessibility. Nothing is
re-created offline: every plug-in, sidechain and automation lane plays
exactly as in the session.

The idea in one line: make a **copy** of the set in which every stem has its
own copy of its group bus, render "All Individual Tracks" once, then sum,
label, trim and check the group renders.

## Requirements

- macOS, Ableton Live 12 (its accessibility support is what makes the dialog scriptable).
- Accessibility permission for the app that runs `osascript` (System Settings → Privacy & Security → Accessibility).
- Python 3 with `numpy` and `soundfile`. macOS's own `python3` usually lacks
  them; make a venv once: `python3 -m venv ~/.venvs/stems && ~/.venvs/stems/bin/pip install -r requirements.txt`
  and run the Python scripts with that interpreter.
- Scripts live in `scripts/` next to this file. Paths below are relative to it.

## Ground rules

- **Never lose the user's work.** Never click "Don't Save" on the user's own set.
  Before Live switches sets, the open set must be saved: save it through
  File → Save Live Set (Live moves the previous version into the project's
  `Backup/` folder) and tell the user you did, or ask first if they might not
  want it saved. Only ever discard changes to *your* export copy, and read the
  dialog's set name before clicking.
- **Never write over the original `.als`.** All restructuring happens in a copy.
- The master/main chain and any "premaster" limiter bus stay out of the stems.
  Group buses (drum bus, bass bus, music bus…) stay in: they are part of the sound.
- Ask the user only for what you can't find out: usually the key (if Live's
  scale isn't set) and who the stems are for (it changes nothing technical).

## Workflow

### 1. Find the set and protect it
```bash
osascript -e 'tell application "System Events" to tell process "Live" to get value of attribute "AXDocument" of window 1'
```
That gives the open set's path. Save it through the menu (see Ground rules):
```bash
osascript -e 'tell application "System Events" to tell process "Live" to click menu item "Save Live Set" of menu "File" of menu bar 1'
```
Then copy the saved `.als` somewhere to work on.

### 2. Read the set
```bash
python3 scripts/inspect_set.py "<set>.als"
```
Shows tempo, Live's scale, loop, locators, the main chain, and every track:
group, on/off, volume, devices (bypassed ones marked), clip spans in bars,
sends, sidechain sources, source files. Things to note:
- **Arrangement range**: first and last audible clip; locators name the sections.
- **Silent tracks**: track off, no active clips, or only disabled clips. Leave them out.
- **Group buses** and their chains, and buses that feed a premaster/limiter track.
- **Sidechain sources** (often muted "ghost" kick/snare tracks). Muted tracks
  still drive sidechains, so leave them exactly as they are.
- **Sends**: if anything sends to a return with effects, decide whether that
  return becomes its own stem (it is not in any track render).

### 3. Name the key and tempo
Use Live's scale (Control bar) if it isn't the C Major default; the
`inspect_set.py` header shows it, and the live value can be read with
`osascript scripts/ax_dump.applescript 1 4` (Control → Scale). Otherwise
look at the MIDI pitch-class summary and run
`python3 scripts/estimate_key.py "<reference master>.wav"`, then confirm
with the user. Write keys as the user writes them (e.g. "D Minor", "Eb").

### 4. Plan the stems
Write a plan (see `references/plan-format.md`). Defaults that work well:
- One stem per distinct part, grouped by **section and role**:
  "Drop 1A-1B Bass Lead", "Drop 2 Sub", "Transition Bass", "Intro Breakbeat".
- Sections come from the locators; split long drops into 8-bar (or 4-bar)
  phrases lettered A, B, C, D.
- **Bass parts are ordered by first appearance.** A part that returns later
  stays in one file ("Drop 1B and 1D Bass Lead").
- Many tiny slices (fills, chops, one-shots) of one sound in one section → one
  "Bass Fills" stem, not twenty.
- Drums: kick, snare/clap, breaks, tops/percussion. A drum bus that only
  holds tops can stay whole ("Top Drums").
- FX and risers: if you can't tell them apart from the session, give each FX
  track its own group copy, then label and merge them after rendering using
  `analyze_renders.py` shapes (rises → riser/sweep, hit+decay → impact/crash,
  steady → atmosphere/texture).
- A bus whose output feeds another track's **sidechain** (e.g. vocals ducking
  the bass) should not be split, or the ducking changes. Keep it as one stem.

### 5. Build the export copy
```bash
python3 scripts/build_export_set.py --als "<saved copy>.als" --plan plan.json \
  --out "<original project folder>/<Set> - STEM EXPORT.als"
```
- Put the copy **inside the original project folder**. Live resolves
  project samples and freeze files relative to the set; a copy elsewhere
  renders those clips as silence (Live's status bar says "Media files are missing").
- The plan's `loop` is only a convenience; the render range is set in the dialog.
- `flatten` dissolves nested groups with no devices; a nested group with
  devices must be split like any other.

### 6. Open it in Live
```bash
open -a "Ableton Live 12 Suite" "<project>/<Set> - STEM EXPORT.als"
```
(Use the edition the user has: `ls /Applications | grep -i ableton`.)
Wait for `End ExchangeDocument` in `~/Library/Preferences/Ableton/Live <version>/Log.txt`.
If a dialog appears, read it with `osascript scripts/ax_dump.applescript 1`
and answer it deliberately (a save prompt for the user's set → stop and go
back to step 1). Then check the status bar has **no** "Media files are missing":
```bash
osascript -e 'tell application "System Events" to tell process "Live" to get name of UI elements of (first UI element of UI element 1 of window 1 whose name is "Status")'
```

### 7. Render
Pick the range: start at the first bar of the arrangement (match the
reference master's start), length to the end plus 2 bars for tails. Note the
dialog's current bit depth so you can put it back afterwards.
```bash
osascript scripts/live_export.applescript "<empty render folder>" <start bar> <length bars> 32 48000
```
It sets All Individual Tracks, the range, 32-bit float, the sample rate,
turns off return/main effects, normalize, loop, mono and video, prints what
Live will render, then confirms the save panel. Live shows an "Export Audio…"
window while rendering (its progress bar is readable with `ax_dump.applescript 1`);
wait until it closes. A 115-track, 3.7-minute song took about 3.5 minutes.
Live writes the files only at the end, so an empty folder mid-render is normal.
Files are named `<Set name> <Track name>.wav`; the group copies are the ones
whose track name starts with `STEM `. Every track is rendered, so expect
roughly 85 MB per track per 4 minutes at 32-bit: check free disk space first.

### 8. Check the renders
```bash
python3 scripts/analyze_renders.py "<render folder>" --bpm <bpm> --start-bar <start> --match " STEM "
```
Every planned stem must be non-silent and play where the session says it
does. A silent stem means a missing sample or a muted track: fix it, don't ship it.

### 9. Finish the pack
Write `finalize.json` (see `references/plan-format.md`) and run:
```bash
python3 scripts/finalize_stems.py finalize.json
```
It sums each stem's sources, orders stems by category then first appearance,
applies one shared trim so the stems' sum peaks near −6 dBFS, cuts every stem
`tail_bars` after the last sound, writes 24-bit WAVs named
`NN <Label> - <Song> - <BPM> BPM - <Key>.wav`, copies the reference master as
`00 Reference Master - …`, checks the reference lines up and resembles the
stem sum, and writes `README.txt` and `stem-qc.json`. Add `"zip": true` for a
ready-to-send archive.

Read the QC: `lag_ms_above_2khz` should be under ~1 ms (it is measured on the
highs because mastering EQ and multiband crossovers delay the lows by several
ms) and `envelope_correlation` above ~0.9. If not, the render range doesn't
match the master, or a part is missing.

### 10. Put everything back and clean up
- Reopen the user's set: `open -a "Ableton Live 12 Suite" "<original>.als"`.
  Live asks whether to save the export copy: confirm the dialog names the
  export copy, then "Don't Save".
- Put the export dialog back the way it was (usually Rendered Track "Main"
  and the user's bit depth): open it, set them, Cancel. Live keeps settings
  changed before a Cancel.
- Move the export copy `.als` out of the project to the Trash and delete the
  raw renders (they are gigabytes).
- Tell the user: where the stems are, the list, the key/BPM used, the trim,
  what was left out as silent, and anything you couldn't verify (you can't
  listen; suggest they solo-check a couple of stems).

## Gotchas
- Live's range fields ignore typed values over accessibility; the script steps them with AXIncrement/AXDecrement.
- Live draws its popup menus as a separate untitled window; the script clicks items there.
- "Undo" history and file times don't prove a set is saved; only Live's save prompt does. Save first.
- Frozen tracks: if their freeze files can't be found Live offers to unfreeze. That only happens with a copy outside the project.
- Group limiters react to what passes through them, so a part printed alone through a bus limiter can come out slightly louder or punchier than in the full mix. Parts that play at the same time and share a bus limiter belong in one stem.
- Rendering takes over Live for a few minutes. Tell the user before you start.

## Customising
- Naming, grouping, headroom, sample rate and category order are all in the
  plan and `finalize.json`; nothing is hard-coded to one genre.
- `references/plan-format.md` documents both files with a worked example.
