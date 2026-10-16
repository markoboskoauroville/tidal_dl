# DELIVERY RECORD - Tidal DL v22 - 8.10.2026

Filled from `python3 gates/run_gates.py` run with pyflakes, shellcheck and vulture present. Re-run it before any later delivery and replace the numbers.

ARTEFACT    `install-macos.sh` (910 lines), `install-termux.sh` (885 lines), generated; on branch `main`
VERSION     new: 22   previous: 21 (legacy/install_tidaldl_v21.sh)

GATES       G1 provenance   pass   2/2 installers fresh and stamped v22; VERSION, installer headers and HANDOFF agree
            G2 secrets      pass   working tree and full history scanned by shape (`AQ.` first): 0 hits
            G3 analysis     pass   py_compile, `bash -n`, pyflakes 0, shellcheck 0 (warning level, on the templates)
            G4 dead code    pass   vulture 0 at >=60%; two unused names found and removed while building
            G5 dead loops   pass   3 while loops, each examined; 7 external waits, 5 with a deadline, 2 without (the download and the login: the person is watching)
            G6 stress       not run
            G7 budgets      not run
            G8 upgrade      pass   Test 4: v21 prefs and 5-field history read by v22; `--setup` over a v21-patched config changes nothing; U key replaces the file in place and keeps the shebang; both generated installers run twice over the top
            G9 record       this document

TESTS       32 checks, 0 red: mechanism 10, real thing 3, ugly cases 10, upgrade 7, termux 2.
            Each test was shown able to fail: five deliberate breakages (AAC accepted as FLAC, shebang lost, URL pattern narrowed, arm64 check removed, quality pin changed) each turned the right test red.
            Found and fixed by the tests: staging folder leak on a failed download; "any key" read in the wrong terminal mode.

LIVE INSTALL     8.10.2026, from a fresh clone of main: the Termux installer was run through the real `curl | bash` URL with only `pkg` stubbed (real venv, real `pip install` of streamrip dev -> streamrip 2.2.0, real `rip`). Exit 0; `tidaldl --version` v22; with no login the command prints the login hint and downloads nothing. Not Android: Linux.

REAL streamrip   `pip install` of streamrip `dev` and `rip config path` were run for real in a sandbox; `tidaldl --setup` was run against the config it generated. The result was inspected line by line.

NOT TESTED
- **No real TIDAL login and no real download.** There is no TIDAL account in this session. The fake `rip` writes real FLAC and AAC files (ffmpeg) and the verification runs on them, but what TIDAL actually serves, the device-code login, and token refresh are unproven. Marko's hand is the test (see below).
- **Nothing ran on a real Mac.** The macOS installer was run on Linux with `uname`, `brew`, `pipx` stubbed to say Darwin/arm64. Unproven: Homebrew installs, `pipx install` of streamrip on macOS, `/opt/homebrew/bin` being writable, `~/.zshrc` PATH handling on a real shell, the `cmd+v` paste in Terminal.app.
- **Real Termux, partial (16.10.2026).** The one-line installer was run on a real Android phone (aarch64, Python 3.14). It installed packages and built streamrip and Pillow, then failed building `pycares`: the bundled c-ares produced no `ares_config.h`. **Fixed in the installer:** `pkg install ... c-ares` plus `PYCARES_USE_SYSTEM_LIB=1` on the `pip install`, so pycares links Termux's system c-ares instead of its bundled copy (see DEVELOPMENT.md). Still unproven on the phone after this fix: that the `pip install` now completes, that `termux-open-url` opens the login page, long-press paste, the layout at phone width, wake lock during a long download (not implemented). A confirming re-run of the one-liner on the phone is the next step.
- **Playlists and artists with hundreds of tracks**: staging holds the whole download in temp space before moving. On a phone with little free space that may run out. Not measured.
- G6 stress (long soak, monkey input) and G7 budgets (start time, memory) were not run.
- The GitHub raw URLs in the README are checked from outside after the push, see the push note in TAKEOVER.md.

MARKO'S TESTS (a hand is needed, marko-tests.md)
1. Mac: run the README line, then `tidaldl`, press `a`, log in to TIDAL in the browser. Expect: the token line shows days left.
2. Mac: paste an album link. Expect: countdown, download, "verified real FLAC", files in `~/Downloads/tidaldl/Artist - Album (Year)`.
3. Phone (Termux): run the README line, then the same two steps. Say what the installer printed if it stops.

KNOWN        Termux wake lock and `termux-notification` on finish are not implemented.
