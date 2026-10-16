# Tidal DL

**macOS (Apple Silicon): install with one line, then run `tidaldl`.**

```sh
curl -fsSL https://raw.githubusercontent.com/markoboskoauroville/tidal_dl/main/install-macos.sh | bash
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-1)

**Termux (Android): install with one line, then run `tidaldl`.**

```sh
pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/markoboskoauroville/tidal_dl/main/install-termux.sh | bash
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-2)

Paste a TIDAL album, track, playlist or artist link and it downloads with [streamrip](https://github.com/nathom/streamrip). A FLAC request is staged and every file is checked with ffprobe before it is saved: if TIDAL serves AAC instead, nothing is saved and no existing file is touched. You have a TIDAL subscription; the app uses your own login and nothing else.

First run, log in once: start the app and press `a`.

```sh
tidaldl
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-3)

Download a link without the menu:

```sh
tidaldl https://tidal.com/album/12345
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-4)

Update from inside the app: press `u`. It shows installed and available version and asks `y`.

Where files go: macOS `~/Downloads/tidaldl`, Termux `~/storage/downloads/tidaldl` (run `termux-setup-storage` once, then run the installer again) or `~/tidaldl`.

## The other documents

| file | read it when |
|---|---|
| [HANDOFF.md](HANDOFF.md) | you pick the app up: the finished state, nothing historical |
| [DEVELOPMENT.md](DEVELOPMENT.md) | you are about to change a decision: every bug and every reason |
| [DELIVERY_RECORD.md](DELIVERY_RECORD.md) | you want to know what was measured and what was not tested |
| [LOCAL_TEST_PROMPT.md](LOCAL_TEST_PROMPT.md) | you want Claude Code on the Mac to test it on the real Mac and an Android emulator |
| [TAKEOVER.md](TAKEOVER.md), [LESSONS.md](LESSONS.md), [momentaryupdates.md](momentaryupdates.md) | the running state, what was learned, the requests word for word |

Run the tests (five, on a real pty, no TIDAL account needed):

```sh
python3 tests/run_all.py
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-5)

Run the delivery gates:

```sh
python3 gates/run_gates.py
```

📋 [Copy this command](https://markoboskoauroville.github.io/tidal_dl/#cmd-6)

Marko Boško · Mantra Productions · Zagreb. Personal use with your own TIDAL subscription.
