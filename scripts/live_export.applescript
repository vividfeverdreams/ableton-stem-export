-- Render "All Individual Tracks" from the set open in Ableton Live 12,
-- driving Live's own Export Audio/Video dialog through macOS accessibility.
-- Needs: Accessibility permission for the app running osascript.
--
-- usage: osascript live_export.applescript <output folder> <start bar> <length bars> [bit depth: 16|24|32] [sample rate]
-- Returns once the export dialog has been confirmed; wait for the
-- "Export Audio..." progress window to close before reading the files.

on findIn(parentEl, roleName, descText)
	tell application "System Events"
		repeat with e in (UI elements of parentEl)
			try
				if (role of e) is roleName and ((description of e as text) is descText or (name of e as text) is descText) then return e
			end try
		end repeat
	end tell
	return missing value
end findIn

on pickFromPopup(pb, itemName)
	tell application "System Events" to tell process "Live"
		click pb
		delay 0.8
		-- Live draws its menus as a separate untitled window whose group holds an AXGroup "menu"
		set m to UI element 1 of group 1 of window 1
		click (first UI element of m whose name is itemName or name is ("✔ " & itemName))
		delay 0.5
	end tell
end pickFromPopup

on turnOffDither(d)
	-- Stems are never dithered: dither belongs once, on the final master.
	tell application "System Events" to tell process "Live"
		set dth to my findIn(d, "AXPopUpButton", "Dither Options")
		if dth is missing value then return "Dither Options not found"
		if (value of dth as text) is "No Dither" then return "No Dither"
		if not (enabled of dth) then return "disabled at this bit depth"
		click dth
		delay 0.8
		set m to UI element 1 of group 1 of window 1
		set seen to ""
		repeat with e in (UI elements of m)
			set nm to (name of e as text)
			set seen to seen & nm & "; "
			if nm contains "No Dither" then
				click e
				delay 0.5
				return "No Dither"
			end if
		end repeat
		key code 53 -- Escape closes the menu
		return "FAILED: no No Dither item in " & seen
	end tell
end turnOffDither

on stepTo(sl, target)
	tell application "System Events"
		set guard to 0
		repeat while ((value of sl) as real) < target and guard < 4000
			perform action "AXIncrement" of sl
			set guard to guard + 1
		end repeat
		repeat while ((value of sl) as real) > target and guard < 8000
			perform action "AXDecrement" of sl
			set guard to guard + 1
		end repeat
	end tell
end stepTo

on setToggle(d, label, wanted)
	tell application "System Events"
		set b to my findIn(d, "AXButton", label)
		if b is missing value then return
		if (value of b as text) is not wanted then click b
		delay 0.2
	end tell
end setToggle

on run argv
	set outDir to item 1 of argv
	set startBar to (item 2 of argv) as real
	set lenBars to (item 3 of argv) as real
	set bitDepth to "32"
	if (count of argv) > 3 then set bitDepth to item 4 of argv
	set sampleRate to ""
	if (count of argv) > 4 then set sampleRate to item 5 of argv

	tell application "System Events" to tell process "Live"
		set frontmost to true
		if not (exists window "Export Audio/Video") then
			click menu item "Export Audio/Video..." of menu "File" of menu bar 1
			delay 2
		end if
		set d to group 1 of window "Export Audio/Video"

		my pickFromPopup(my findIn(d, "AXPopUpButton", "Rendered Track Chooser"), "All Individual Tracks")
		set d to group 1 of window "Export Audio/Video"

		repeat with nm in {"Start of Rendered Audio File (Beat)", "Start of Rendered Audio File (Sixteenths)"}
			my stepTo(my findIn(d, "AXSlider", nm as text), 1)
		end repeat
		repeat with nm in {"Length of Rendered Audio File (Beat)", "Length of Rendered Audio File (Sixteenths)"}
			my stepTo(my findIn(d, "AXSlider", nm as text), 0)
		end repeat
		my stepTo(my findIn(d, "AXSlider", "Start of Rendered Audio File (Bar)"), startBar)
		my stepTo(my findIn(d, "AXSlider", "Length of Rendered Audio File (Bar)"), lenBars)

		my setToggle(d, "Include Return and Main Effects", "Off")
		my setToggle(d, "Render as Loop", "Off")
		my setToggle(d, "Convert to Mono", "Off")
		my setToggle(d, "Normalize", "Off")
		my setToggle(d, "Create Analysis File", "Off")
		my setToggle(d, "Encode PCM", "On")
		my setToggle(d, "Encode MP3", "Off")
		my setToggle(d, "Create Video with Rendered Audio", "Off")

		set ft to my findIn(d, "AXPopUpButton", "File Type")
		if (value of ft as text) is not "WAV" then my pickFromPopup(ft, "WAV")
		set bd to my findIn(d, "AXPopUpButton", "Recording Bit Depth")
		if (value of bd as text) is not bitDepth then my pickFromPopup(bd, bitDepth)
		if sampleRate is not "" then
			set srb to my findIn(d, "AXPopUpButton", "Sample Rate")
			if (value of srb as text) is not sampleRate then my pickFromPopup(srb, sampleRate)
		end if
		set ditherState to my turnOffDither(group 1 of window "Export Audio/Video")
		if ditherState starts with "FAILED" or (bitDepth is not "32" and ditherState is not "No Dither") then
			return "STOPPED, nothing exported: could not turn dither off (" & ditherState & ")"
		end if

		-- read back what Live will render
		set d to group 1 of window "Export Audio/Video"
		set summary to ""
		repeat with e in (UI elements of d)
			try
				if (role of e) is in {"AXPopUpButton", "AXSlider", "AXButton"} and (value of e) is not missing value then
					set summary to summary & (description of e as text) & "=" & (value of e as text) & "; "
				end if
			end try
		end repeat

		set summary to summary & "Dither=" & ditherState & "; "

		click (my findIn(d, "AXButton", "Export"))
		delay 2
		-- native save panel: Go to Folder, then confirm with Return
		perform action "AXRaise" of window "Save"
		keystroke "g" using {command down, shift down}
		delay 1
		keystroke outDir
		delay 0.5
		key code 36
		delay 1.5
		perform action "AXRaise" of window "Save"
		key code 36
		delay 2
		if exists window "Save" then
			-- e.g. a "Replace existing files?" confirmation
			return "CHECK: save panel still open. " & summary
		end if
		return summary
	end tell
end run
