#!/usr/bin/env python3
"""
Fantasy Lamy z Panamy – FPL Data Fetcher v2
Stahuje H2H výsledky + picks (výběr hráčů, kapitáni, chipy) pro všechny manažery.
Spouští se přes GitHub Actions každou hodinu.
"""

import json, time, os, requests
from datetime import datetime, timezone
from collections import defaultdict

# ─── KONFIGURACE ─────────────────────────────────────────────────────────────
LEAGUE_ID      = 83735
CURRENT_SEASON = "2024/25"
REGULAR_GWS    = 36   # základní část GW1–36

MANAGERS = {
    4239832: {"name": "Martin Holub",     "team": "Real Mordor *****",  "short": "MH"},
    156572:  {"name": "Libor Pechoč",     "team": "Četnické humoresky", "short": "LP"},
    155266:  {"name": "Martin Válek",     "team": "Fusswaffe",          "short": "MV"},
    167387:  {"name": "Jaroslav Bureš",   "team": "Yobagoya",           "short": "JB"},
    138950:  {"name": "Rudolf Kvapil",    "team": "EREKCE ZE STRACHU",  "short": "RK"},
    472208:  {"name": "Marek Palán",      "team": "Eskimo brothers",    "short": "MP"},
    184202:  {"name": "Michal Krautwurm", "team": "Krampus",            "short": "MK"},
    4127653: {"name": "Lukáš Kapinus",    "team": "1. FC Lukasovo",     "short": "LK"},
}

BASE_URL = "https://fantasy.premierleague.com/api"
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer":         "https://fantasy.premierleague.com/",
}
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# ─────────────────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def get(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  ⚠ pokus {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def fetch_bootstrap():
    print("📥 Bootstrap...")
    # Nejdřív načti hlavní stránku pro cookies
    session.get("https://fantasy.premierleague.com/", timeout=10)
    time.sleep(0.5)
    data = get(f"{BASE_URL}/bootstrap-static/")
    if data:
        gws_done = [e["id"] for e in data["events"] if e.get("finished")]
        print(f"   Hráčů PL: {len(data['elements'])}, hotových GW: {len(gws_done)}")
    return data


def fetch_league_matches():
    print("📥 H2H zápasy ligy...")
    matches, seen, page = [], set(), 1
    while True:
        data = get(f"{BASE_URL}/leagues-h2h-matches/league/{LEAGUE_ID}/?page={page}")
        if not data:
            break
        for m in data.get("results", []):
            if m["id"] not in seen:
                seen.add(m["id"])
                matches.append(m)
        print(f"   strana {page}: {len(data['results'])} zápasů, has_next={data['has_next']}")
        if not data.get("has_next"):
            break
        page += 1
        time.sleep(0.4)
    print(f"   ✅ {len(matches)} unikátních zápasů")
    return matches


def fetch_all_picks(max_gw):
    """Stáhne picks pro každého manažera v každém GW."""
    print(f"📥 Picks všech manažerů (GW1–{max_gw})...")
    all_picks = {}
    for entry, info in MANAGERS.items():
        print(f"   {info['name']}...", end=" ", flush=True)
        all_picks[entry] = {}
        ok = 0
        for gw in range(1, max_gw + 1):
            data = get(f"{BASE_URL}/entry/{entry}/event/{gw}/picks/")
            if data:
                all_picks[entry][gw] = {
                    "active_chip":     data.get("active_chip"),
                    "entry_history":   data.get("entry_history", {}),
                    "picks":           data.get("picks", []),
                }
                ok += 1
            time.sleep(0.15)
        print(f"{ok} GW")
    return all_picks


def get_current_gw(bootstrap):
    for e in bootstrap.get("events", []):
        if e.get("is_current"):
            return e["id"]
    finished = [e["id"] for e in bootstrap.get("events", []) if e.get("finished")]
    return max(finished) if finished else 38


# ─── VÝPOČTY ──────────────────────────────────────────────────────────────────

def compute_standings(matches):
    players = {e: {**info, "entry": e, "pts": 0, "w": 0, "d": 0, "l": 0,
                   "fpl_total": 0, "results": []}
               for e, info in MANAGERS.items()}
    regular = [m for m in matches if not m.get("is_knockout") and m["event"] <= REGULAR_GWS]
    for m in sorted(regular, key=lambda x: x["event"]):
        for pfx in ["entry_1", "entry_2"]:
            e = m[f"{pfx}_entry"]
            if e not in players:
                continue
            pts_l = m[f"{pfx}_total"]
            pts_f = m[f"{pfx}_points"]
            players[e]["pts"]       += pts_l
            players[e]["fpl_total"] += pts_f
            r = "W" if pts_l == 3 else "D" if pts_l == 1 else "L"
            players[e]["results"].append({"gw": m["event"], "result": r, "fpl": pts_f})
            if pts_l == 3:   players[e]["w"] += 1
            elif pts_l == 1: players[e]["d"] += 1
            else:            players[e]["l"] += 1
    for p in players.values():
        p["results"].sort(key=lambda x: x["gw"])
        p["form"] = [r["result"] for r in p["results"][-5:]]
    return sorted(players.values(), key=lambda x: (-x["pts"], -x["fpl_total"]))


def compute_h2h(matches):
    entries = list(MANAGERS.keys())
    h2h = {e: {o: {"w": 0, "l": 0, "d": 0} for o in entries if o != e} for e in entries}
    regular = [m for m in matches if not m.get("is_knockout") and m["event"] <= REGULAR_GWS]
    for m in regular:
        e1, e2 = m["entry_1_entry"], m["entry_2_entry"]
        p1, p2 = m["entry_1_total"], m["entry_2_total"]
        if e1 not in h2h or e2 not in h2h:
            continue
        if p1 == 3:   h2h[e1][e2]["w"] += 1; h2h[e2][e1]["l"] += 1
        elif p2 == 3: h2h[e2][e1]["w"] += 1; h2h[e1][e2]["l"] += 1
        else:         h2h[e1][e2]["d"] += 1; h2h[e2][e1]["d"] += 1
    return {str(k): {str(o): v for o, v in vv.items()} for k, vv in h2h.items()}


def compute_records(matches):
    regular = [m for m in matches if not m.get("is_knockout") and m["event"] <= REGULAR_GWS]
    scores = []
    for m in regular:
        for pfx in ["entry_1", "entry_2"]:
            e   = m[f"{pfx}_entry"]
            opp = "entry_2" if pfx == "entry_1" else "entry_1"
            scores.append({
                "pts":   m[f"{pfx}_points"],
                "name":  MANAGERS.get(e, {}).get("name", "?"),
                "team":  MANAGERS.get(e, {}).get("team", "?"),
                "entry": e,
                "gw":    m["event"],
                "opp":   MANAGERS.get(m[f"{opp}_entry"], {}).get("name", "?"),
            })
    scores.sort(key=lambda x: -x["pts"])
    return {"top10": scores[:10], "bottom5": list(reversed(scores[-5:]))}


def compute_series(standings):
    out = []
    for p in standings:
        res = "".join(r["result"] for r in p["results"])
        bw, bl, cw, cl = 0, 0, 0, 0
        for c in res:
            if c == "W":   cw += 1; bw = max(bw, cw); cl = 0
            elif c == "L": cl += 1; bl = max(bl, cl); cw = 0
            else:          cw = 0;  cl = 0
        cur_c = res[-1] if res else ""
        cur_n = 0
        for c in reversed(res):
            if c == cur_c: cur_n += 1
            else: break
        out.append({"entry": p["entry"], "name": p["name"],
                    "best_w": bw, "best_l": bl,
                    "current": f"{cur_n}× {cur_c}" if cur_c else "–"})
    return out


def compute_playout_gw37(matches, standings):
    order   = [p["entry"] for p in standings]
    pts_map = {p["entry"]: p["pts"] for p in standings}
    sf_pairs = [(order[4], order[7]), (order[5], order[6])]
    gw37 = {}
    for m in matches:
        if m["event"] == 37:
            gw37[m["entry_1_entry"]] = m["entry_1_points"]
            gw37[m["entry_2_entry"]] = m["entry_2_points"]
    results = []
    for higher, lower in sf_pairs:
        naskok  = pts_map[higher] - pts_map[lower]
        h_fpl   = gw37.get(higher, 0)
        l_fpl   = gw37.get(lower, 0)
        h_virt  = h_fpl + naskok
        winner  = higher if h_virt > l_fpl else lower
        results.append({
            "higher": {**MANAGERS[higher], "entry": higher,
                       "league_pts": pts_map[higher], "gw37_fpl": h_fpl,
                       "naskok": naskok, "virtual": h_virt},
            "lower":  {**MANAGERS[lower],  "entry": lower,
                       "league_pts": pts_map[lower],  "gw37_fpl": l_fpl,
                       "naskok": 0, "virtual": l_fpl},
            "winner": winner,
            "loser":  lower if winner == higher else higher,
        })
    return results


def compute_picks_stats(all_picks, pl_players, max_gw):
    """
    Ze surových picks spočítá:
    - Nejobíbenější hráči (nejvíce GW v sestavě napříč ligou)
    - Nejčastější kapitáni
    - Nejlepší/nejhorší kapitánská volba (dle bodů)
    - Chipy – kdy kdo použil
    - Per-manažer statistiky: oblíbení hráči, nejlepší GW, kapitánský rekord
    """

    # Celkové statistiky ligy
    pl_appearances = defaultdict(int)   # hráč → počet GW v sestavách (všichni manažeři)
    captain_count  = defaultdict(int)   # hráč → počet kapitánství
    captain_pts    = defaultdict(list)  # hráč → list bodů když byl kapitán

    # Per-manažer
    manager_stats = {}

    for entry, gws in all_picks.items():
        m_appearances = defaultdict(int)
        m_captain     = defaultdict(int)
        m_cap_pts     = []
        m_chips       = {}
        m_gw_pts      = {}
        m_best_cap    = {"pts": 0, "player": "", "gw": 0}
        m_worst_cap   = {"pts": 999, "player": "", "gw": 0}

        for gw, data in gws.items():
            gw = int(gw)
            chip = data.get("active_chip")
            if chip:
                m_chips[gw] = chip

            eh = data.get("entry_history", {})
            gw_pts = eh.get("points", 0)
            m_gw_pts[gw] = gw_pts

            for pick in data.get("picks", []):
                pid  = pick["element"]
                pos  = pick["position"]   # 1–11 = sestava, 12–15 = lavička
                mult = pick.get("multiplier", 1)
                is_cap = pick.get("is_captain", False)

                if pos <= 11:  # pouze základní sestava
                    m_appearances[pid] += 1
                    pl_appearances[pid] += 1

                if is_cap:
                    m_captain[pid] += 1
                    captain_count[pid] += 1
                    # Body kapitána = GW body * multiplikátor (2 nebo 3)
                    # Ale máme jen celkové body manažera, ne body jednoho hráče
                    # → pro kapitánské body použijeme entry_history pokud dostupné
                    # Lepší aproximace: uložíme GW a hráče, body dotáhneme z pl_players
                    cap_name = pl_players.get(str(pid), {}).get("web_name", f"ID{pid}")
                    m_cap_pts.append({"gw": gw, "player_id": pid,
                                      "player": cap_name, "gw_total": gw_pts})
                    captain_pts[pid].append(gw_pts)

        # Seřaď oblíbené hráče
        top_players = sorted(m_appearances.items(), key=lambda x: -x[1])[:15]
        top_captains = sorted(m_captain.items(), key=lambda x: -x[1])[:5]

        manager_stats[str(entry)] = {
            "top_players":   [{"id": pid, "name": pl_players.get(str(pid), {}).get("web_name", f"ID{pid}"), "gws": n}
                               for pid, n in top_players],
            "top_captains":  [{"id": pid, "name": pl_players.get(str(pid), {}).get("web_name", f"ID{pid}"), "times": n}
                               for pid, n in top_captains],
            "chips":         m_chips,
            "gw_points":     m_gw_pts,
            "cap_history":   m_cap_pts,
            "best_gw":       max(m_gw_pts.items(), key=lambda x: x[1]) if m_gw_pts else (0, 0),
            "worst_gw":      min(m_gw_pts.items(), key=lambda x: x[1]) if m_gw_pts else (0, 0),
        }

    # Globální TOP hráči ligy
    top_liga = sorted(pl_appearances.items(), key=lambda x: -x[1])[:20]
    top_caps  = sorted(captain_count.items(),  key=lambda x: -x[1])[:10]

    return {
        "top_players_liga": [
            {"id": pid, "name": pl_players.get(str(pid), {}).get("web_name", f"ID{pid}"), "appearances": n}
            for pid, n in top_liga
        ],
        "top_captains_liga": [
            {"id": pid, "name": pl_players.get(str(pid), {}).get("web_name", f"ID{pid}"), "times": n}
            for pid, n in top_caps
        ],
        "per_manager": manager_stats,
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"\n🦙 Fantasy Lamy z Panamy – Data Fetcher v2")
    print(f"   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    bootstrap  = fetch_bootstrap()
    if not bootstrap:
        print("❌ Bootstrap selhal – zkusím znovu za hodinu")
        return

    current_gw = get_current_gw(bootstrap)
    max_regular = min(current_gw, REGULAR_GWS)
    print(f"   GW: {current_gw} (základní část do GW{REGULAR_GWS})")

    # PL hráči jako slovník id → jméno
    pl_players = {str(p["id"]): {"web_name": p["web_name"], "team": p["team"],
                                  "element_type": p["element_type"],
                                  "total_points": p["total_points"]}
                  for p in bootstrap["elements"]}

    matches   = fetch_league_matches()
    standings = compute_standings(matches)
    h2h       = compute_h2h(matches)
    records   = compute_records(matches)
    playout   = compute_playout_gw37(matches, standings)
    series    = compute_series(standings)

    playoff_sf    = [m for m in matches if m.get("is_knockout") and m["event"] == 37]
    playoff_final = [m for m in matches if m.get("is_knockout") and m["event"] == 38]

    # Picks – stáhni pro GW1 až aktuální (max 38)
    fetch_max = min(current_gw, 38)
    all_picks   = fetch_all_picks(fetch_max)
    picks_stats = compute_picks_stats(all_picks, pl_players, fetch_max)

    output = {
        "meta": {
            "updated_at":    datetime.now(timezone.utc).isoformat(),
            "current_gw":    current_gw,
            "season":        CURRENT_SEASON,
            "league_id":     LEAGUE_ID,
            "total_matches": len(matches),
        },
        "standings":               [p for p in standings],
        "h2h":                     h2h,
        "records":                 records,
        "series":                  series,
        "playoff": {
            "shiva_sf":    [
                {"home": {"entry": m["entry_1_entry"], "name": m["entry_1_player_name"],
                          "team": m["entry_1_name"], "gw37_fpl": m["entry_1_points"]},
                 "away": {"entry": m["entry_2_entry"], "name": m["entry_2_player_name"],
                          "team": m["entry_2_name"], "gw37_fpl": m["entry_2_points"]},
                 "winner": m.get("winner")}
                for m in playoff_sf
            ],
            "shiva_final": [
                {"home": {"entry": m["entry_1_entry"], "name": m["entry_1_player_name"],
                          "team": m["entry_1_name"], "gw38_fpl": m["entry_1_points"]},
                 "away": {"entry": m["entry_2_entry"], "name": m["entry_2_player_name"],
                          "team": m["entry_2_name"], "gw38_fpl": m["entry_2_points"]},
                 "winner": m.get("winner")}
                for m in playoff_final
            ],
            "playout_sf":  playout,
        },
        "picks_stats": picks_stats,
        "pl_players":  pl_players,
    }

    out_path = os.path.join(DATA_DIR, "season.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    size = os.path.getsize(out_path) / 1024
    print(f"\n✅ Uloženo: {out_path} ({size:.1f} KB)")


if __name__ == "__main__":
    main()
