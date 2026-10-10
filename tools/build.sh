#!/bin/sh
# Builds the launcher stub and the probes as static x86-64 Windows programs (needs mingw-w64, e.g. Homebrew's).
# Output: build/EpicGamesLauncher.exe, build/wkill.exe, build/sdg.exe, build/wfocus.exe
set -e
cd "$(dirname "$0")/.."
mkdir -p build
CC=x86_64-w64-mingw32-gcc
FLAGS="-O2 -static -mwindows -Wall -Wno-unused-parameter"
$CC $FLAGS -municode -o build/EpicGamesLauncher.exe tools/launcher/egl.c -lntdll
$CC $FLAGS -municode -o build/wkill.exe tools/probes/wkill.c -lntdll
$CC $FLAGS -o build/sdg.exe tools/probes/stackdump.c -lpsapi
$CC $FLAGS -municode -o build/wfocus.exe tools/probes/wfocus.c
ls -l build/*.exe
