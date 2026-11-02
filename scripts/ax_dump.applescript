-- Dump the accessibility tree of one of Live's windows.
-- usage: osascript ax_dump.applescript <window index> [max depth]
on dump(e, ind, depth, maxDepth)
	tell application "System Events"
		set s to ""
		try
			set s to ind & (role of e) & " | " & (description of e as text) & " | " & (name of e as text) & " | " & (value of e as text) & linefeed
		on error
			try
				set s to ind & (role of e) & " | " & (description of e as text) & linefeed
			end try
		end try
		if depth < maxDepth then
			try
				repeat with c in (UI elements of e)
					set s to s & my dump(c, ind & "  ", depth + 1, maxDepth)
				end repeat
			end try
		end if
		return s
	end tell
end dump
on run argv
	set idx to (item 1 of argv) as integer
	set maxDepth to 8
	if (count of argv) > 1 then set maxDepth to (item 2 of argv) as integer
	tell application "System Events" to tell process "Live"
		return my dump(window idx, "", 0, maxDepth)
	end tell
end run
