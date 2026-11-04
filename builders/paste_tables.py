"""Paste-ready NHL puck line tables for the CMS (no iframe, no scripts).

Reads site/nhl/puck-line/data.json (written by nhl_puck_line.py) and writes:
  site/nhl/puck-line/paste-current.html   this season, refreshed daily, paste when you want to update
  site/nhl/puck-line/paste-previous.html  last season incl. closing-price P/L, paste once per season
  site/nhl/puck-line/paste-current.tsv    same as paste-current, opens in Excel / copy into the CMS table tool
  site/nhl/puck-line/paste-previous.tsv
Plain <table> markup with light inline styles, so it still reads fine if the CMS strips styles.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "site", "nhl", "puck-line")


def pct(v):
    return "-" if v is None else f"{v*100:.1f}%"


def units(v):
    if v is None:
        return "-"
    return "0.0u" if abs(v) < 0.05 else f"{v:+.1f}u"


def label(rate):
    if rate is None:
        return "-"
    return "Wide" if rate >= 0.62 else ("Tight" if rate < 0.50 else "Average")


TH = 'style="text-align:left;padding:6px 8px;border-bottom:2px solid #1C2633"'
THR = 'style="text-align:right;padding:6px 8px;border-bottom:2px solid #1C2633"'
TD = 'style="text-align:left;padding:6px 8px;border-bottom:1px solid #e3e6ea"'
TDR = 'style="text-align:right;padding:6px 8px;border-bottom:1px solid #e3e6ea"'


def build(d, which):
    prev = which == "previous"
    season = d["previous_season"] if prev else d["current_season"]
    heads = ["Team", "Margin", "Wins", "Won by 2+", "Needed ENG", "OT/SO wins", "-1.5 cover", "+1.5 cover"]
    if prev:
        heads += ["-1.5 P/L", "+1.5 P/L"]
    rows = []
    for t in d["teams"]:
        s = t[which]
        lab = label(s["win_by_2_pct"]) if prev else t["tier"]
        r = [t["name"], lab, str(s["wins"]) + ("*" if (not prev and s["wins"] < 10) else ""), pct(s["win_by_2_pct"]), pct(s["needed_eng_pct"]),
             pct(s["otso_win_pct"]), pct(s["cover_minus_15_pct"]), pct(s["cover_plus_15_pct"])]
        if prev:
            p = t.get("previous_prices") or {}
            r += [units((p.get("minus") or {}).get("units")), units((p.get("plus") or {}).get("units"))]
        rows.append((s["win_by_2_pct"] or 0, r))
    rows.sort(key=lambda x: -x[0])
    lg = d["league"][which]
    note = (f"{season} regular season. Won by 2+ = share of wins by two or more goals (league: {pct(lg['win_by_2_pct'])}). "
            "Needed ENG = share of those that needed an empty-net goal. Margin: Wide 62%+, Average 50-62%, Tight under 50%.")
    if prev:
        note += " P/L = 1 unit on that team every game at DraftKings closing prices. Past results, not a prediction."
    else:
        note += f" Margin blends this season with last. * Fewer than 10 wins, small sample. Games through {d['data_through']}."
    html = ['<div style="overflow-x:auto;-webkit-overflow-scrolling:touch">',
            '<table style="width:100%;min-width:680px;border-collapse:collapse;font-size:14px">',
            f"<caption style=\"text-align:left;font-weight:700;padding:0 0 6px\">NHL puck line profile, {season}</caption>",
            "<thead><tr>" + "".join(f"<th {TH if i < 2 else THR}>{h}</th>" for i, h in enumerate(heads)) + "</tr></thead><tbody>"]
    for _, r in rows:
        html.append("<tr>" + "".join(f"<td {TD if i < 2 else TDR}>{c}</td>" for i, c in enumerate(r)) + "</tr>")
    lr = ["League average", "", "", pct(lg["win_by_2_pct"]), pct(lg["needed_eng_pct"]), pct(lg["otso_win_pct"]),
          pct(lg["cover_minus_15_pct"]), pct(lg["cover_plus_15_pct"])] + (["", ""] if prev else [])
    html.append("<tr>" + "".join(f"<td {TD if i < 2 else TDR}><strong>{c}</strong></td>" for i, c in enumerate(lr)) + "</tr>")
    html.append("</tbody></table></div>")
    html.append(f'<p style="font-size:12px;color:#5b6573">{note} Source: NHL, ExpertPicks Lab.</p>')
    tsv = "\n".join(["\t".join(heads)] + ["\t".join(r) for _, r in rows] + ["\t".join(lr)]) + "\n"
    return "\n".join(html) + "\n", tsv


def main():
    with open(os.path.join(OUT, "data.json")) as f:
        d = json.load(f)
    for which, name in (("current", "current"), ("previous", "previous")):
        html, tsv = build(d, which)
        open(os.path.join(OUT, f"paste-{name}.html"), "w").write(html)
        open(os.path.join(OUT, f"paste-{name}.tsv"), "w").write(tsv)
    print("wrote paste tables")


if __name__ == "__main__":
    main()
