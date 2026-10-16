# HANDOFF
Version: 22
Repository: https://github.com/markoboskoauroville/tidal_dl
Latest artefacts: `install-macos.sh`, `install-termux.sh` on `main` (generated; no release tags yet)
The reasons behind every choice, and every bug, are in [`DEVELOPMENT.md`](DEVELOPMENT.md). This file is only the finished state.

## What it is
`tidaldl` is a terminal app: paste a TIDAL link, it downloads with streamrip, checks with ffprobe that the file is a real FLAC, and only then puts it in the download folder. One command, one source file (`tidaldl.py`), two platforms: macOS on Apple Silicon (arm64 only) and Termux on Android.

## The model
- `tidaldl.py` is the only copy of the program. `install-macos.sh` and `install-termux.sh` are generated from it and `src/*.sh.in` by `tools/build_installers.py`. `--check` fails when they are stale.
- streamrip (`rip`) does the downloading and owns the TIDAL login. The login token lives in streamrip's `config.toml`, never in this repository.
- A FLAC request is downloaded into a temporary staging folder, every audio file is probed, and only real FLAC (plus cover art) is moved into the download folder. Anything else is left behind. An existing file is never overwritten by a fallback.

## Where things are
| | macOS | Termux |
|---|---|---|
| command | `~/.local/bin/tidaldl` or `/opt/homebrew/bin/tidaldl` | `$PREFIX/bin/tidaldl` |
| streamrip | pipx | venv `~/.local/share/tidaldl/venv`, `rip` linked into `$PREFIX/bin` |
| streamrip config | `~/Library/Application Support/streamrip/config.toml` | `~/.config/streamrip/config.toml` |
| downloads | `~/Downloads/tidaldl` | `~/storage/downloads/tidaldl`, else `~/tidaldl` |
| prefs, history | `~/.config/tidaldl/` | `~/.config/tidaldl/` |

Environment overrides (used by the tests): `TIDALDL_CONFIG`, `TIDALDL_DIR`, `TIDALDL_PREFS`, `TIDALDL_UPDATE_URL`.

## Keys
Arrow up/down and space choose the quality (AAC 320 or FLAC 16/44.1, FLAC is the default). Paste starts a 10 second countdown, `q` cancels, space starts now. `h` help, `a` authorization (clears the token and logs in again), `u` update, `q` quit.

## Files
| file | job |
|---|---|
| `tidaldl.py` | the app. `VERSION` is the one place the number lives |
| `src/macos.sh.in`, `src/termux.sh.in` | installer templates |
| `tools/build_installers.py` | generates the two installers |
| `tests/` | the five tests, `python3 tests/run_all.py` |
| `gates/run_gates.py` | the delivery gates with counts |
| `legacy/install_tidaldl_v21.sh` | the original macOS installer, kept for the upgrade test |

## Building a new version
Edit `tidaldl.py`, raise `VERSION` by one (every change is a new number), run `python3 tools/build_installers.py`, update the version line above, run `python3 gates/run_gates.py`, commit and push. The U key in a running app reads `tidaldl.py` from `main`.

## What has never been proven
See [`DELIVERY_RECORD.md`](DELIVERY_RECORD.md), NOT TESTED. In short: no real TIDAL login or download has been run, nothing has run on a real Mac or in real Termux.
