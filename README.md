# rugby-form-guide

The fixtures ahead in any rugby competition, with each team's recent form, points scored and conceded, home and away record, and the head-to-head, in one command.

```
╭─ USA Perpignan v Montpellier ──────────────────────────────────────────────╮
│ Sat 26 Sep, 14:00 UTC                                                      │
│                                                                            │
│ USA Perpignan             · L W L L   ██░░░░░░░░ 1/5 won                   │
│                           scores 25.0 conc 43.5  home 1-0-0  away 0-0-3    │
│ Montpellier               W W L L W   ██████░░░░ 3/5 won                   │
│                           scores 19.9 conc 20.4  home 3-0-3  away 1-0-3    │
│                                                                            │
│ Met 3x  ░░░░░░░░░░░░  USA Perpignan 0  drawn 0  Montpellier 3              │
│ Last met 2026-09-19: Montpellier 50-13 USA Perpignan                       │
╰────────────────────────────────────────────────────────────────────────────╯
```

Built on the [rugbyAPI](https://rugbyapi.com) public API. Python 3.9 or newer, standard library only: nothing to install.

## Run it

```
python form_guide.py
```

1. The first run asks for your API key (free at [rugbyapi.com](https://rugbyapi.com/login)) and saves it to `~/.rugbyapi/key`, so you are only asked once.
2. The key is checked against `/v1/usage` before any work, and your plan and remaining lookups are shown.
3. Pick a competition with the arrow keys and Enter.
4. The guide prints every fixture in the next 14 days.

Straight to a competition, or further ahead:

```
python form_guide.py --competition "Top 14"
python form_guide.py --competition "United Rugby Championship" --days 30
```

## What each line means

| | |
|---|---|
| `W W L L W` | The last five results, newest on the right. A dot means fewer than five on record. |
| bar, `3/5 won` | Wins in those five. |
| `scores` / `conc` | Average points scored and conceded over the last ten matches. |
| `home` / `away` | Won-drawn-lost over the last ten, split by venue. |
| `Met 3x` | Every finished meeting on record; the bar is the first team's share of wins. |

## Plans and lookups

Form and head-to-head read past seasons, so the full guide needs the **Archive** plan. A free key covers yesterday, today and the fixtures ahead; the tool tells you so rather than failing.

Each run uses roughly two lookups per team plus one per fixture. Answers are cached in `./data` (fixtures for 30 minutes, form and head-to-head for 6 hours), so running it again costs little. The tool paces itself from the `X-RateLimit-Remaining` header and slows down as your daily allowance runs low.

## JSON for your own code

```
python form_guide.py --competition cp_1ACRS3C --json > guide.json
```

Prints only the document: no prompts, no progress. It never asks for anything, so it runs from cron. It names the criteria it used (competition, days ahead, how form and averages were counted, what was excluded) so the file explains itself later. Set `RUGBYAPI_KEY` in the environment if no key is saved yet.

Exit codes: `0` done, `1` key refused or network problem, `2` bad arguments, `3` your plan does not include form (Archive needed).

## Licence

MIT. The data belongs to rugbyAPI's terms: https://rugbyapi.com/legal/terms
