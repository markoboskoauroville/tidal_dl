# Local test prompt

For Marko's own computer: open Claude Code in an empty folder, paste the whole block below, and let it run. It tests Tidal DL on the real Mac and in a real Android emulator, fixes what it finds, and reports. Written 8.10.2026 for v22.

```text
You are testing Tidal DL v22 for Marko Boško on this Mac (MacBook Pro, Apple M1 Pro, arm64) and in the Android emulator he has installed. Repository: https://github.com/markoboskoauroville/tidal_dl (public, branch main). Marko is not at the computer: do every step yourself and report what really happened. Never claim a step passed unless you saw its output.

RULES (Marko's Mantra manifest, markoboskoauroville/MANTRA_MANIFEST, private; if you have a token, read START_HERE.md and modules/four-tests.md and modules/delivery-gate.md first):
- Never print, log or commit a key or token. Do not ask for, type or store TIDAL credentials. The real TIDAL login is Marko's hand: when you reach it, stop that step, mark it NOT TESTED, and carry on.
- Do not touch Marko's mouse or keyboard on this Mac more than needed. If you must drive the Mac's screen, say by voice (POST http://127.0.0.1:8837/speak) "Marko, I need the computer", and wait for him to type done. Never start the voice server yourself.
- Every code change is a new whole-number VERSION in tidaldl.py (v23, v24, ...). After a change: python3 tools/build_installers.py, python3 tests/run_all.py, python3 gates/run_gates.py, then commit and push to main, then fetch the raw URL and confirm the bytes match.

PART A - THE MAC
1. git clone https://github.com/markoboskoauroville/tidal_dl into a new empty folder. Run: uname -m (must say arm64), python3 tests/run_all.py, python3 gates/run_gates.py. Report the counts.
2. Install exactly as the README says, from the live URL, with the real Homebrew, pipx and streamrip:
   curl -fsSL https://raw.githubusercontent.com/markoboskoauroville/tidal_dl/main/install-macos.sh | bash
   Run it a second time over the top and confirm it is clean and ~/.zshrc has the PATH line only once. Then: tidaldl --version (v22), rip --version, ls ~/Downloads/tidaldl, and read the [tidal] section of ~/Library/Application Support/streamrip/config.toml showing only quality = 2 and download_videos = false (do not print the token fields).
3. Run tidaldl in a pty (script, expect or Python pty, not Marko's Terminal window): check the header shows v22, press h and q. Run tidaldl https://tidal.com/album/1 with no login and confirm it prints the login hint and downloads nothing.
4. Real login and a real download are Marko's hand. Do not attempt them. Mark NOT TESTED.

PART B - ANDROID EMULATOR (real Termux)
1. adb devices. If no emulator is running, list AVDs with emulator -list-avds and start one headless-or-windowed (Android 10+; 4 GB RAM; 8 GB data). Wait for adb shell getprop sys.boot_completed to say 1. Check internet in the emulator.
2. Download the universal Termux APK from https://github.com/termux/termux-app/releases (latest, the file named termux-app_*_universal.apk), adb install it, launch it (adb shell am start -n com.termux/.app.TermuxActivity), wait for the first-run bootstrap to finish (screenshot with adb exec-out screencap -p until the prompt shows). If the GitHub build cannot run on this emulator image, say so and try the F-Droid build.
3. To type commands into Termux use whichever works: the RUN_COMMAND intent (needs allow-external-apps=true in ~/.termux/termux.properties, so first type that line once through adb shell input text), or adb shell input text with %s for spaces. Capture results by redirecting output to a file under /sdcard or ~ and adb pull, or by screenshot. Say which method worked.
4. In Termux run the README line exactly:
   pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/markoboskoauroville/tidal_dl/main/install-termux.sh | bash
   This is the most likely thing to fail: streamrip's dependencies may have to compile. If it fails, get the FULL log, find the real cause, fix install-termux.sh in src/termux.sh.in (never in the generated file), bump VERSION, rebuild, test, push, and rerun in the emulator until it passes. Run it a second time over the top and confirm it is clean.
5. In Termux confirm: tidaldl --version, rip --version, head -1 $PREFIX/bin/tidaldl (shebang is Termux's python3), ls -l $PREFIX/bin/rip (a link into ~/.local/share/tidaldl/venv/bin).
6. In Termux run the repository's own tests on the real Android Python: git clone https://github.com/markoboskoauroville/tidal_dl && cd tidal_dl && python3 tests/run_all.py. Report the counts; any failure is a finding (the installer-run tests may need the sandbox stubs, say which tests were skipped and why).
7. Start tidaldl in Termux, take a screenshot: check the menu fits a phone-width screen, keys h and q work, and a pasted TIDAL link (use adb shell input text with a link such as https://tidal.com/album/1) shows the countdown and q cancels it. With no login it must print the login hint.
8. Press u in tidaldl (Termux): it should say v22 is current.
9. The TIDAL login (press a) and a real download need Marko's TIDAL account: do not attempt. Mark NOT TESTED.

REPORT
Fix every real finding in the repository (source files only), keep the manifest's rules (version bump, tests, gates, push, fetch back). Then update DELIVERY_RECORD.md: move each thing you verified from NOT TESTED to MEASURED with what you ran and the counts, and leave the rest NOT TESTED with the reason. Append the bugs you found to DEVELOPMENT.md (symptom, cause, cost, fix). Commit and push to main. Finish with a short report to Marko: what passed, what failed and was fixed, what only he can test (the TIDAL login and one real download on the Mac and on the phone).
```
