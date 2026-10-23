' Starts the DoseWISE dev supervisor with no window. Used by the "DoseWISE servers" scheduled task
' (at sign-in and every 5 minutes) and by start-dosewise.bat. If it's already running, the new copy
' exits immediately, so running this again is always safe.
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = root
sh.Run "node """ & root & "\scripts\dev.mjs"" all", 0, False
