"""Auswertung: Netzbau, Slope-Scaling-Lauf mit den gewählten Optionen, Optimum (HiGHS), Urteil, Verteilung und Experiment-Tabellen."""

import statistics as st
from dataclasses import dataclass
from typing import NamedTuple

import ss_constants as C
import ss_formulation as fm
import ss_model as md
import ss_slope as sl


class NetParams(NamedTuple):
    net: str
    k: int
    p: int
    d: int
    s: int
    density: int
    spread: int
    load: int
    fix: int
    seed: int
    gw: int
    gh: int
    gdensity: int
    gcap: int
    gdem: int
    gseed: int


class Opts(NamedTuple):
    start: str
    memory: str
    perturb: str
    polish: str
    damping: float
    iters: int
    control: str


DEFAULT_PARAMS = NetParams(C.DEFAULT_NET, C.DEFAULT_K, C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD, C.DEFAULT_FIX, C.DEFAULT_SEED,
                           C.DEFAULT_GW, C.DEFAULT_GH, C.DEFAULT_GDENSITY, C.DEFAULT_GCAP, C.DEFAULT_GDEM, C.DEFAULT_GSEED)
DEFAULT_OPTS = Opts(C.DEFAULT_START, C.DEFAULT_MEMORY, C.DEFAULT_PERTURB, C.DEFAULT_POLISH, C.DEFAULT_DAMPING, C.DEFAULT_ITER, C.DEFAULT_CONTROL)


def normalise(p):
    """Feste Netze ignorieren alle Regler der Zufallsnetze; das Streckennetz die des Distributionsnetzes und umgekehrt (gleicher Schlüssel für den Zwischenspeicher)."""
    if p.net in C.FIXED_NETS:
        return DEFAULT_PARAMS._replace(net=p.net, k={"bigm": 1, "rounding": 1, "bundle": 2}[p.net])
    if p.net == "grid":
        return p._replace(p=C.DEFAULT_P, d=C.DEFAULT_D, s=C.DEFAULT_S, density=C.DEFAULT_DENSITY, spread=C.DEFAULT_SPREAD, load=C.DEFAULT_LOAD, seed=C.DEFAULT_SEED)
    return p._replace(gw=C.DEFAULT_GW, gh=C.DEFAULT_GH, gdensity=C.DEFAULT_GDENSITY, gcap=C.DEFAULT_GCAP, gdem=C.DEFAULT_GDEM, gseed=C.DEFAULT_GSEED)


def build(p):
    if p.net == "bigm":
        return md.bigm_net()
    if p.net == "rounding":
        return md.rounding_net()
    if p.net == "bundle":
        return md.bundle_net()
    if p.net == "grid":
        return md.generate_design_grid(p.gw, p.gh, p.gdensity, p.gcap, p.gdem, p.k, p.gseed, p.fix)
    return md.generate_design(p.p, p.d, p.s, p.density, p.spread, p.load, p.seed, p.k, p.fix)


def with_seed(p, seed):
    return p._replace(gseed=seed) if p.net == "grid" else p._replace(seed=seed)


def run(design, start="cap", memory="off", perturb="on", polish="on", damping=0.0, iters=C.DEFAULT_ITER, control="normal", problem=None):
    return sl.slope_scaling(design, start=start, memory=memory == "on", perturb=perturb == "on", damping=damping, max_iter=iters, keep_best=control != "last", adapt=control != "once",
                            problem=problem, do_polish=polish == "on")


@dataclass(frozen=True)
class Analysis:
    params: NetParams
    opts: Opts
    design: object
    feasible: bool
    opt: object = None              # Solution des exakten MIP (HiGHS)
    result: object = None           # SlopeResult
    upper: float = None             # Aufrunden aus dem Vorgängerstück (obere Schranke)


def analyse(params, opts=DEFAULT_OPTS):
    params = normalise(params)
    design = build(params)
    try:
        strong, opt = fm.solve_lp(design, fm.STRONG), fm.solve_mip(design)
    except fm.Infeasible:
        return Analysis(params, opts, design, False)
    result = run(design, *opts)
    return Analysis(params, opts, design, True, opt, result, fm.round_up(design, strong)[0])


def result_cost(r, polished):
    return r.polished_cost if polished else r.best_cost


def verdict(a):
    """(Stufe, Code, Daten): ok (Lücke < 0,5 %: das Optimum getroffen) / gap (Lücke) / nothing (nicht lieferbar)."""
    if not a.feasible:
        return "warning", "nothing", {}
    r, opt = a.result, a.opt.objective
    final = r.polished_cost
    d = {"opt": opt, "best": r.best_cost, "polished": final, "gap_best": r.best_cost / opt - 1, "gap": final / opt - 1, "iterations": r.iterations, "stop": r.stop, "best_iteration": r.best_iteration,
         "last": r.last_cost, "gap_last": r.last_cost / opt - 1, "seconds": r.seconds, "highs_seconds": a.opt.seconds, "groups": a.design.G, "open": len(r.polished_design), "opt_open": a.opt.n_open,
         "upper": a.upper, "gap_upper": a.upper / opt - 1, "polish_gain": r.best_cost - final, "first": r.frames[0].true_cost, "gap_first": r.frames[0].true_cost / opt - 1}
    if d["gap"] < 5e-3:
        return "success", "exact", d
    return "success", "ok", d


# --- Verteilung über feste Netze --------------------------------------------------------------------------------------------------------

def distribution(params, opts=DEFAULT_OPTS, seeds=C.QUALITY_SEEDS):
    """Lücke zum Optimum (Anteil), Iterationen, Stoppgrund und Vergleich mit dem Aufrunden über feste Netze derselben Art; nicht lieferbare Netze werden gezählt, nicht gemittelt."""
    rows, infeasible = [], 0
    for seed in seeds:
        a = analyse(with_seed(params, seed), opts)
        if not a.feasible:
            infeasible += 1
            continue
        d = verdict(a)[2]
        rows.append(dict(seed=seed, gap=d["gap"], gap_best=d["gap_best"], gap_first=d["gap_first"], gap_last=d["gap_last"], gap_upper=d["gap_upper"], iterations=d["iterations"], stop=d["stop"],
                         seconds=d["seconds"], highs=d["highs_seconds"], groups=d["groups"], best_iteration=d["best_iteration"]))
    col = lambda key: [r[key] for r in rows]
    mean = lambda key: st.mean(col(key)) if rows else float("nan")
    return dict(n_seeds=len(seeds), n_feasible=len(rows), n_infeasible=infeasible, cols={k: col(k) for k in ("gap", "gap_best", "gap_first", "gap_last", "gap_upper", "iterations")},
                gap_mean=mean("gap"), gap_median=st.median(col("gap")) if rows else float("nan"), gap_max=max(col("gap")) if rows else float("nan"), gap_best_mean=mean("gap_best"), gap_first_mean=mean("gap_first"),
                gap_last_mean=mean("gap_last"), gap_upper_mean=mean("gap_upper"), iterations_mean=mean("iterations"), iterations_median=st.median(col("iterations")) if rows else float("nan"),
                exact_share=(sum(1 for g in col("gap") if g < 5e-3) / len(rows)) if rows else float("nan"), last_worse_share=(sum(1 for r in rows if r["gap_last"] > r["gap_best"] + 1e-9) / len(rows)) if rows else float("nan"),
                stops={s: sum(1 for r in rows if r["stop"] == s) for s in ("fixed", "cycle", "limit")}, seconds_mean=mean("seconds"), highs_mean=mean("highs"), better_than_upper=sum(1 for r in rows if r["gap"] < r["gap_upper"] - 1e-9))


# --- Experimente ---------------------------------------------------------------------------------------------------------------------

VARIANTS = (
    ("Reines Slope Scaling", dict(polish="off", perturb="off", damping=0.0)),
    ("+ Politur", dict(polish="on", perturb="off", damping=0.0)),
    ("+ Gedächtnis", dict(polish="on", perturb="off", damping=0.0, memory="on")),
    ("+ Störung", dict(polish="on", perturb="on", damping=0.0)),
    ("+ Dämpfung 0,5", dict(polish="on", perturb="off", damping=0.5)),
    ("Startsteigung Nachfrage", dict(polish="on", perturb="on", damping=0.0, start="demand")),
    ("Dämpfung + Störung (Standard)", dict(polish="on", perturb="on", damping=0.5)),
)


def variant_table(params, seeds=C.VARIANT_SEEDS):
    """Lücke, Anteil exakter Netze, Iterationen und Zyklen je Variante auf festen Netzen (Standardgröße)."""
    nets = []
    for seed in seeds:
        d = build(normalise(with_seed(params, seed)))
        try:
            opt = fm.solve_mip(d).objective
        except fm.Infeasible:
            continue
        nets.append((d, opt, sl.Problem(d)))
    rows = []
    for name, kw in VARIANTS:
        gaps, iters, stops = [], [], []
        for d, opt, prob in nets:
            r = run(d, problem=prob, **kw)
            gaps.append(r.polished_cost / opt - 1 if kw.get("polish", "on") == "on" else r.best_cost / opt - 1)
            iters.append(r.iterations)
            stops.append(r.stop)
        rows.append(dict(name=name, gap=st.mean(gaps), exact=sum(1 for g in gaps if g < 5e-3), n=len(gaps), iterations=st.mean(iters), cycle=sum(1 for s in stops if s == "cycle"), gap_max=max(gaps)))
    return dict(n=len(nets), rows=rows)


def control_table(params, seeds=C.VARIANT_SEEDS):
    """Negativkontrollen (Lücke): wie beschrieben, nur ein LP, letzte statt beste Iteration, jeweils ohne Politur."""
    nets = []
    for seed in seeds:
        d = build(normalise(with_seed(params, seed)))
        try:
            nets.append((d, fm.solve_mip(d).objective, sl.Problem(d)))
        except fm.Infeasible:
            continue
    out = {}
    for control in ("normal", "once", "last"):
        gaps = []
        for d, opt, prob in nets:
            r = run(d, polish="off", perturb="off", control=control, problem=prob)
            gaps.append(r.best_cost / opt - 1)
        out[control] = dict(gap=st.mean(gaps), exact=sum(1 for g in gaps if g < 5e-3), n=len(gaps), worst=max(gaps))
    return out


def size_table(params, sizes=C.SIZES, seeds=C.SIZE_SEEDS, limit=C.HIGHS_LIMIT, per_size=2):
    """Slope Scaling (Standardoptionen) gegen HiGHS über wachsende Netze: Entwurfskanten, Lücke, Sekunden beider; HiGHS mit Zeitlimit (Kosten = beste gefundene Lösung)."""
    out = []
    for P, D, S in sizes:
        rows = []
        for seed in seeds:
            d = md.generate_design(P, D, S, params.density, params.spread, params.load, seed, params.k, params.fix)
            try:
                opt = fm.solve_mip(d, time_limit=limit)
            except fm.Infeasible:
                continue
            r = run(d, iters=60)
            rows.append((d.G, r.polished_cost / opt.objective - 1, r.seconds, opt.seconds))
            if len(rows) == per_size:
                break
        out.append(dict(size=(P, D, S), n=len(rows), groups=st.mean(x[0] for x in rows) if rows else float("nan"), gap=st.mean(x[1] for x in rows) if rows else float("nan"),
                        seconds=st.mean(x[2] for x in rows) if rows else float("nan"), highs=st.mean(x[3] for x in rows) if rows else float("nan")))
    return out


# --- Anzeige-Helfer ------------------------------------------------------------------------------------------------------------------

def arc_name(design, e):
    net = design.net
    return f"{net.names[net.arcs[e][0]]} → {net.names[net.arcs[e][1]]}"


def group_name(design, g):
    return arc_name(design, design.arcs_of(g)[0])


def frame_words(design, frame, previous=None, top=3):
    """Was sich in dieser Iteration geändert hat: die Kanten, die der Entwurf neu öffnet oder schließt."""
    prev = previous.design if previous is not None else frozenset()
    opened = sorted(frame.design - prev)[:top]
    closed = sorted(prev - frame.design)[:top]
    parts = []
    if opened:
        parts.append("neu offen: " + ", ".join(group_name(design, g) for g in opened) + (" …" if len(frame.design - prev) > top else ""))
    if closed:
        parts.append("geschlossen: " + ", ".join(group_name(design, g) for g in closed) + (" …" if len(prev - frame.design) > top else ""))
    return "; ".join(parts) if parts else "derselbe Entwurf wie zuvor"
