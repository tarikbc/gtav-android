@echo off
rem Put the Rockstar launcher's old CEF profile back (Renderer.bak -> Renderer, the current one becomes Renderer.new).
rem The profile holds the "remembered device" cookies: without it Rockstar asks for an email code at every start.
rem Wine renames the folder even while the launcher has it open; the next launcher start uses the restored one.
set R=%USERPROFILE%\Documents\Rockstar Games\Social Club\Launcher
dir /b "%R%" > D:\gtav-android\scratch\ew_r.txt 2>&1
ren "%R%\Renderer" Renderer.new >> D:\gtav-android\scratch\ew_r.txt 2>&1
ren "%R%\Renderer.bak" Renderer >> D:\gtav-android\scratch\ew_r.txt 2>&1
echo after: >> D:\gtav-android\scratch\ew_r.txt
dir /b "%R%" >> D:\gtav-android\scratch\ew_r.txt 2>&1
