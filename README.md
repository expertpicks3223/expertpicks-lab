# ExpertPicks Lab

Self-updating data tables for ExpertPicks resource articles. Each table is a static page
hosted on GitHub Pages and embedded in the CMS with an iframe. A scheduled GitHub Action
rebuilds the data every day, so nobody has to edit the article.

## NHL Puck Line Profile

- Page: https://expertpicks3223.github.io/expertpicks-lab/nhl/puck-line/
- Data: `site/nhl/puck-line/data.json` and `data.csv` (same folder on Pages)
- Builder: `builders/nhl_puck_line.py` (Python stdlib only, reads the public NHL API)
- Schedule: `.github/workflows/nhl-puck-line.yml`, daily at 09:00 UTC, plus a manual "Run workflow" button

### Embed code (paste into the CMS HTML block)

```html
<iframe src="https://expertpicks3223.github.io/expertpicks-lab/nhl/puck-line/"
  width="100%" height="760" style="border:0;max-width:100%" loading="lazy"
  title="NHL Puck Line Profile"></iframe>
```

Options: add `?theme=dark` for the dark version. The page also posts its height to the
parent window (`ep-lab-height` message) if the dev team wants auto-resizing later.

### What the columns mean

- Won by 2+: share of the team's wins decided by two or more goals (a -1.5 winner)
- Needed ENG: share of those 2+ wins where the empty-net goal created the margin
- OT/SO wins: share of wins that came in overtime or a shootout (always a one-goal result)
- -1.5 cover / +1.5 cover: share of all games where the team covered that line
- Tier: Friendly / Neutral / Risky. Blends this season with last season (20-win prior) so
  early-season tiers do not swing on a handful of games. Friendly >= 62%, Risky < 50%.

### Yearly maintenance (once a season)

Nothing to change. The builder reads the current season from the NHL standings feed and
uses the previous season as the baseline automatically. Update the article's fixed
baseline paragraph once in the summer if you want to quote the newly finished season.

### Datawrapper option

Datawrapper can read the CSV directly: Upload data > Link external dataset >
`https://expertpicks3223.github.io/expertpicks-lab/nhl/puck-line/data.csv`.
See https://www.datawrapper.de/academy/live-updating-options

### Moving to the site servers later

Copy `site/` to any static host (Cloudflare Pages, an expertpicks.com subdomain such as
lab.expertpicks.com) and point the workflow's deploy step there. Then this repo can be
made private again. The builder can also move into the private sports-data pipeline and
read Supabase once nothing public sits next to the database credentials.

### Note on GitHub schedules

GitHub pauses scheduled workflows in public repos after 60 days without commits. The daily
data commit keeps it active during the season. In the summer, re-enable it from the
Actions tab if it pauses.
