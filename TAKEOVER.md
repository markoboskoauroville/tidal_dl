# Takeover

State on 8.10.2026: Tidal DL v22 is built, tested and on GitHub (public). The app is `tidaldl.py`; the macOS (Apple Silicon) and Termux installers are generated from it. Read [HANDOFF.md](HANDOFF.md) first.

Tests: `python3 tests/run_all.py` (30 checks, green). Gates: `python3 gates/run_gates.py`.

Next: Marko tests with his own hand (list in DELIVERY_RECORD.md): the real TIDAL login and one real download on the Mac, then on the phone. Whatever he reports goes into `momentaryupdates.md`. Open items: Termux wake lock and a finish notification, tags for releases if wanted.
