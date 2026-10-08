# DEVELOPMENT
Appended, never rewritten. Present state is in [HANDOFF.md](HANDOFF.md).

## Part one: the bugs, by shape

### A temporary folder that only one exit cleans up
- **Symptom:** nothing visible. `tidaldl_stage_*` folders pile up in the temp directory.
- **Cause (inherited from v21):** the staging folder was removed inside the branch where `rip` succeeded. When `rip` exited non-zero, or the app was told nothing was produced, the folder stayed.
- **Cost:** a full album of FLAC data left in `/tmp` after every failed download.
- **Fix, v22:** the staging folder is removed after the result is decided, on every path. Test 3 asserts no `tidaldl_stage_*` is left after a failure, an AAC fallback, and success. The test failed on v21 behaviour before the fix.

### Verifying one file and trusting the rest
- **Symptom:** an album where one track falls back to AAC could be saved with an AAC track inside, labelled "verified real FLAC".
- **Cause (inherited):** only the newest audio file of the staging folder was probed.
- **Fix, v22:** `promote_flac` probes every audio file, moves real FLAC and non-audio extras (cover art), leaves everything else, and reports how many tracks were refused and as what. A file named `.flac` that ffprobe says is AAC is refused (Test 1 and 3).
- **ffprobe missing:** v21 treated that as "not FLAC" for every file, so a missing ffprobe made every FLAC download fail as "FLAC not available". v22 trusts the extension only when ffprobe is absent.

### A key that says "any key" in a mode that needs Enter
- **Symptom:** after the `a` (authorization) screen the app waited for Enter, not any key.
- **Cause (inherited):** the terminal was put back to normal mode for the login subprocess and the final "press any key" was read in that mode.
- **Fix, v22:** single-key mode is entered just for the final key. The new update screen stays in single-key mode throughout. Found when Test 2/4 drove the update screen on a pty and the key was echoed instead of read.

### An installer step that waits for a person
- **Symptom (by reading, not observed on a Mac):** `rip config open` in the v21 installer opens streamrip's config in an editor, which can block an installer run.
- **Fix, v22:** `rip config path` prints the path and creates the default file without opening anything. Verified against the real streamrip `dev` in a sandbox: it creates `config.toml`, and `tidaldl --setup` patches exactly the intended keys (quality and download_videos only inside `[tidal]`, other providers untouched).

### The update that cannot be anonymous and the file that was cut in half
- Not a bug here, but written down because the manifest paid for it (termux-app.md §10): the updater validates size, shebang, parse **and an end marker** (`# end of tidaldl`), because a parse check passes on some truncated files. Test 3 feeds it half a file and expects "nothing was changed".
- The updater keeps the installed file's first line, because on Termux it is rewritten to Termux's python and a verbatim overwrite would break the command (Test 4).

## Part two: decisions, and what was rejected

| decision | rejected | why |
|---|---|---|
| One source file, `tidaldl.py`, platform detected at runtime; installers generated from it | a Python copy per platform; or the Python written inside the shell script by hand | two copies with a rule about keeping them in step are still two copies (manifest README rule 1). `--check` fails when stale. |
| macOS target is arm64 only; the installer refuses Intel | supporting both | the-machine.md, 14.9.2026: Marko's Mac is an M1 Pro. Homebrew path `/opt/homebrew`. An override exists for testing only. |
| The patcher lives in `tidaldl --setup`, not in a heredoc of the installer | keeping v21's inline Python | one tested function for both installers |
| Updater reads `tidaldl.py` from `main` | `git pull` | the installed command is a single file, not a clone (termux-app.md); no git needed on the Mac |
| Termux: streamrip in a venv with `--system-site-packages`, Pillow from `pkg` | `pipx` (not in Termux's repos); building Pillow with pip | Pillow is the package most likely to fail to compile on a phone |
| Termux shebang rewritten to `$PREFIX/bin/python3` | `#!/usr/bin/env python3` | Termux has no `/usr/bin/env` without termux-exec |
| Termux download folder: shared storage if `~/storage/downloads` exists, else `~/tidaldl` | forcing `termux-setup-storage` | it needs a person's tap; the installer says so |
| The command is written beside its name and renamed over the top | `cat >` straight onto the command | truncating a running script (termux-app.md §4) |
| No release tags or APK-style versions yet | tagging every version | the app updates from `main`; a tag per version can be added the day a release is needed. The number is in `VERSION`, the installer header and HANDOFF. |
| v21's quality choice (AAC / FLAC), countdown, colours, keys kept as they were | redesign | it is Marko's working interface (never back to zero) |

## Part three: the versions
| version | what |
|---|---|
| 21 | Marko's single macOS installer (legacy/install_tidaldl_v21.sh) |
| 22 | repository created; Termux support; arm64 check; `--setup`, `--version`; U key update; every-file FLAC verification; staging cleanup on failure; version shown in the header; four tests, gates |

## Part four: what was inherited
- All of the v21 interface and download logic, extracted verbatim from the installer and then changed as listed above.
- streamrip is not vendored: it is installed from its `dev` branch, as v21 did.
- Not carried across: v21's `set -e` + `>/dev/null 2>&1` around the pipx install, which hid the reason for a failure from the person; the message is now the pipx error.
