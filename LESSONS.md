# Lessons

Nothing learned goes in here that is not true.

## 8.10.2026
- **Where the Mantra rules are.** "Mantra manifest" is the private repository `MANTRA_MANIFEST` (start at `START_HERE.md`); "Mantra intro manifest" is the public `MANIFEST_INTRO`. A cloud session sees neither until they are attached with `add_repo`; `list_repos` shows them. Searching the disk first wasted time.
- **A test that passes first time proves nothing yet.** Five deliberate breakages were needed to show the four tests can fail.
- **A pty test finds what unit tests cannot.** The "press any key" screens were reading in the wrong terminal mode; only a real pty showed it.
- **The fake external tool must produce the real thing.** The fake `rip` writes genuine FLAC and AAC with ffmpeg, so the ffprobe check is exercised for real.
