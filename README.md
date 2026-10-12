# Claude Usage

A small Mac menu bar app that shows how much of your Claude plan you've used,
right next to the battery icon. Same numbers as `/usage` in Claude Code.

- Current 5-hour session % and a countdown to its reset, in the menu bar
- Weekly limits (all models, Opus, Sonnet) and their reset times in the menu
- Turns orange at 75% and red at 90%
- Refreshes every minute; optional start at login

Made by **Afif Tabish**.

## Download

Get the `.dmg` for your Mac from the [Releases](../../releases/latest) page:

- **Apple Silicon** (M1 or later): `Claude-Usage-<version>-apple-silicon.dmg`
- **Intel**: `Claude-Usage-<version>-intel.dmg`

Not sure which one you have? Apple menu → About This Mac → "Chip" or "Processor".

Needs macOS 11 or later, and [Claude Code](https://claude.com/claude-code)
installed and logged in on the same Mac.

## Install

1. Open the `.dmg` and drag **Claude Usage** into **Applications**.
2. The first time, right-click the app → **Open** → **Open**. (It isn't from
   the App Store, so macOS asks once.) If macOS only offers "Move to Trash" or
   "Done": System Settings → Privacy & Security → scroll down → **Open Anyway**.
3. If macOS asks to use "Claude Code-credentials", click **Always Allow**.
4. Click the icon in the menu bar → turn on **Start at login** if you like.

Tip: hold ⌘ and drag the icon to move it next to the battery.

## Privacy

The app reads the Claude login that Claude Code already saved on your Mac
(Keychain item "Claude Code-credentials") and sends it only to
`api.anthropic.com` to fetch your usage. The token is never written to disk or
logged. If the login has expired, opening Claude Code once renews it.

## Build it yourself

```bash
./build_dmg.sh
```

This makes `dist/Claude-Usage-<version>-<arch>.dmg` for the kind of Mac you
run it on. To try the app with sample numbers instead of your login:
`CLAUDE_USAGE_MOCK=1 .venv/bin/python usage_bar.py`.

Releases are built by GitHub Actions: push a tag such as `v1.0` and both DMGs
are attached to a new release.

## License

MIT © 2026 Afif Tabish
