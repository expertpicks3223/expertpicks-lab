"""NHL Puck Line Profile builder for the ExpertPicks Lab.

Answers, for every NHL team:
  * When they win, how often is it by 2+ goals (a -1.5 cover)?
  * How often did that 2+ margin need an empty-net goal?
  * How often do their wins come in OT or a shootout (which can never cover -1.5)?
  * Across all games, how often do they cover -1.5 and +1.5?

Source: the public NHL web API (https://api-web.nhle.com/v1/score/YYYY-MM-DD), the same
official feed the ExpertPicks sports-data pipeline uses. Standard library only.

Outputs:
  data/nhl/puck_line_games_<season>.csv   one row per team-game (cache, refreshed with a 7-day overlap)
  site/nhl/puck-line/data.json            what the embed table reads
  site/nhl/puck-line/data.csv             flat copy (works as a Datawrapper live-data source)
"""
import csv, json, os, sys, time, datetime as dt, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "nhl")
OUT = os.path.join(ROOT, "site", "nhl", "puck-line")
API = "https://api-web.nhle.com/v1"
OVERLAP_DAYS = 7          # re-fetch the last week each run so stat corrections are picked up
TIER_PRIOR_WINS = 20      # how many "last season wins" the tier blends in (keeps tiers stable early season)
TIER_FRIENDLY = 0.62      # blended won-by-2+ rate at or above this = "Wide" (wins by 2+ often)
TIER_RISKY = 0.50         # below this = "Tight" (wins tend to be close)
FIELDS = ["season", "date", "game_id", "team", "opp", "home", "gf", "ga", "eng", "last_period"]

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ExpertPicksLab/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise RuntimeError(f"failed {url}: {e}")
            time.sleep(2 * (i + 1))

def seasons():
    s = get(f"{API}/standings-season")["seasons"]
    today = dt.date.today().isoformat()
    started = [x for x in s if x["standingsStart"] <= today]
    return started[-2], started[-1]          # previous, current

def day_rows(day):
    rows = []
    for g in get(f"{API}/score/{day}").get("games", []):
        if g.get("gameType") != 2 or g.get("gameState") not in ("OFF", "FINAL"):
            continue
        h, a = g["homeTeam"], g["awayTeam"]
        eng = {h["abbrev"]: 0, a["abbrev"]: 0}
        for gl in g.get("goals", []):
            if gl.get("goalModifier") in ("empty-net", "awarded-empty-net") and gl.get("teamAbbrev") in eng:
                eng[gl["teamAbbrev"]] += 1
        lp = (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")
        for t, o, home in ((h, a, 1), (a, h, 0)):
            rows.append(dict(season=g["season"], date=g["gameDate"], game_id=g["id"], team=t["abbrev"], opp=o["abbrev"],
                             home=home, gf=t["score"], ga=o["score"], eng=eng[t["abbrev"]], last_period=lp))
    return rows

def load_cache(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [dict(r, game_id=int(r["game_id"]), home=int(r["home"]), gf=int(r["gf"]), ga=int(r["ga"]), eng=int(r["eng"]))
                for r in csv.DictReader(f)]

def refresh(season, is_current):
    path = os.path.join(DATA, f"puck_line_games_{season['id']}.csv")
    rows = load_cache(path)
    start = dt.date.fromisoformat(season["standingsStart"])
    end = min(dt.date.fromisoformat(season["standingsEnd"]), dt.date.today() - dt.timedelta(days=1))
    if rows and not is_current:
        return rows                                   # finished season, already cached
    if rows:
        last = max(dt.date.fromisoformat(r["date"]) for r in rows)
        start = max(start, last - dt.timedelta(days=OVERLAP_DAYS))
    days = []
    d = start
    while d <= end:
        days.append(d.isoformat()); d += dt.timedelta(days=1)
    with ThreadPoolExecutor(8) as ex:
        fresh = [r for rs in ex.map(day_rows, days) for r in rs]
    keep = {(r["game_id"], r["team"]): r for r in rows}
    for r in fresh:
        keep[(r["game_id"], r["team"])] = r
    rows = sorted(keep.values(), key=lambda r: (r["date"], r["game_id"], r["team"]))
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"{season['id']}: {len(rows)//2} games cached ({len(days)} days fetched)")
    return rows

def pct(n, d):
    return round(n / d, 4) if d else None

def profile(rows):
    gp = len(rows)
    wins = [r for r in rows if r["gf"] > r["ga"]]
    two = [r for r in wins if r["gf"] - r["ga"] >= 2]
    needed = [r for r in two if r["gf"] - r["ga"] - r["eng"] < 2]
    otso = [r for r in wins if r["last_period"] != "REG"]
    plus15 = [r for r in rows if r["gf"] - r["ga"] >= -1]
    return dict(gp=gp, wins=len(wins), won_by_2=len(two),
                win_by_2_pct=pct(len(two), len(wins)),
                needed_eng_pct=pct(len(needed), len(two)),
                otso_win_pct=pct(len(otso), len(wins)),
                cover_minus_15_pct=pct(len(two), gp),
                cover_plus_15_pct=pct(len(plus15), gp))

def tier(cur, prev):
    prior = prev["win_by_2_pct"] if prev and prev["win_by_2_pct"] is not None else 0.568
    blended = (cur["won_by_2"] + TIER_PRIOR_WINS * prior) / (cur["wins"] + TIER_PRIOR_WINS)
    label = "Wide" if blended >= TIER_FRIENDLY else ("Tight" if blended < TIER_RISKY else "Average")
    return label, round(blended, 4)

def team_names():
    try:
        st = get(f"{API}/standings/now")["standings"]
        return {t["teamAbbrev"]["default"]: t["teamName"]["default"] for t in st}
    except Exception:
        return {}

def main():
    prev_s, cur_s = seasons()
    prev_rows = refresh(prev_s, False)
    cur_rows = refresh(cur_s, True)
    names = team_names()
    # Fixed closing-price results for the finished season (built once from historical odds, see builders/README)
    pf = os.path.join(DATA, f"puck_line_prices_{prev_s['id']}.json")
    prices = json.load(open(pf)) if os.path.exists(pf) else {}
    league_prev, league_cur = profile(prev_rows), profile(cur_rows)
    teams = sorted({r["team"] for r in prev_rows} | {r["team"] for r in cur_rows})
    out = []
    for t in teams:
        p = profile([r for r in prev_rows if r["team"] == t]) if any(r["team"] == t for r in prev_rows) else None
        c = profile([r for r in cur_rows if r["team"] == t])
        lab, blended = tier(c, p)
        out.append(dict(team=t, name=names.get(t, t), current=c, previous=p, tier=lab, tier_score=blended,
                        previous_prices=prices.get("teams", {}).get(t)))
    data_through = max((r["date"] for r in cur_rows), default=None)
    fmt = lambda s: f"{str(s['id'])[:4]}-{str(s['id'])[6:]}"
    payload = dict(resource="NHL Puck Line Profile", updated_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                   data_through=data_through, current_season=fmt(cur_s), previous_season=fmt(prev_s),
                   league=dict(current=league_cur, previous=league_prev),
                   tier_rules=dict(prior_wins=TIER_PRIOR_WINS, friendly=TIER_FRIENDLY, risky=TIER_RISKY),
                   previous_prices=prices.get("league"), prices_source=prices.get("source"),
                   source="NHL (api-web.nhle.com)", teams=out)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "data.json"), "w") as f:
        json.dump(payload, f, indent=1)
    with open(os.path.join(OUT, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Team", "Tier", f"Wins {payload['current_season']}", "Won by 2+ %", "2+ wins that needed ENG %", "OT/SO wins %",
                    "Covers -1.5 (all games) %", "Covers +1.5 (all games) %", f"Won by 2+ % {payload['previous_season']}"])
        for t in sorted(out, key=lambda x: -x["tier_score"]):
            c, p = t["current"], t["previous"] or {}
            r = lambda v: "" if v is None else round(v * 100, 1)
            w.writerow([t["name"], t["tier"], c["wins"], r(c["win_by_2_pct"]), r(c["needed_eng_pct"]), r(c["otso_win_pct"]),
                        r(c["cover_minus_15_pct"]), r(c["cover_plus_15_pct"]), r(p.get("win_by_2_pct"))])
    print(f"wrote {len(out)} teams, data through {data_through}")

if __name__ == "__main__":
    sys.exit(main())
