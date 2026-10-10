@echo off
rem Turn on GTA V's built-in benchmark: -benchmark -benchmarkFrameTimes in commandline.txt next to GTA5.exe (A:).
rem Keeps a copy of an existing file as commandline.txt.before. Remove the switches again after the series, or the
rem game runs the benchmark at every start.
if exist A:\commandline.txt (echo existing: > D:\gtav-android\scratch\ew_r.txt & type A:\commandline.txt >> D:\gtav-android\scratch\ew_r.txt) else (echo no commandline.txt before > D:\gtav-android\scratch\ew_r.txt)
if exist A:\commandline.txt copy /y A:\commandline.txt A:\commandline.txt.before >nul
echo -benchmark -benchmarkFrameTimes> A:\commandline.txt
echo now: >> D:\gtav-android\scratch\ew_r.txt
type A:\commandline.txt >> D:\gtav-android\scratch\ew_r.txt
