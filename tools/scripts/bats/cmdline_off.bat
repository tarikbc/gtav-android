@echo off
rem Turn the built-in benchmark off again: delete commandline.txt next to GTA5.exe (A:) or restore the copy
rem cmdline_on.bat kept.
if exist A:\commandline.txt.before (move /y A:\commandline.txt.before A:\commandline.txt >nul & echo restored commandline.txt.before > D:\gtav-android\scratch\ew_r.txt) else (del A:\commandline.txt & echo removed commandline.txt > D:\gtav-android\scratch\ew_r.txt)
