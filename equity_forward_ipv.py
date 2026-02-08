import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

"""Equity Forward IPV check: carry vs put–call parity with PASS/FAIL and net-carry diagnostics."""


# -----------------------------
# Inputs
# -----------------------------
@dataclass(frozen=True)
class EquityForwardIPVInputs:
    spot: float                  # S0
    r: float                     # discount rate (continuous comp)
    net_carry: float             # q = dividend yield - repo/borrow (continuous comp)
    T: float                     # year fraction to maturity
    strike: float                # K
    call: Optional[float] = None # C(K,T)
    put: Optional[float] = None  # P(K,T)


# -----------------------------
# Validation
# -----------------------------
def validate_inputs(x: EquityForwardIPVInputs) -> None:
    if x.spot <= 0:
        raise ValueError("spot must be > 0")
    if x.strike <= 0:
        raise ValueError("strike must be > 0")
    if x.T <= 0:
        raise ValueError("T must be > 0")
    if x.call is not None and x.call < 0:
        raise ValueError("call must be >= 0")
    if x.put is not None and x.put < 0:
        raise ValueError("put must be >= 0")
    if (x.call is None) ^ (x.put is None):
        raise ValueError("provide both call and put (same K,T), or neither")


# -----------------------------
# Core formulas (continuous comp)
# -----------------------------
def forward_carry(spot: float, r: float, net_carry: float, T: float) -> float:
    """Baseline: F = S0 * exp((r - net_carry) * T)."""
    return spot * math.exp((r - net_carry) * T)


def forward_from_put_call_parity(K: float, C: float, P: float, r: float, T: float) -> float:
    """Market-implied: F = K + exp(rT) * (C - P)."""
    return K + math.exp(r * T) * (C - P)


def implied_net_carry(spot: float, F_target: float, r: float, T: float) -> Optional[float]:
    """
    Diagnostic: solve net_carry q such that forward_carry(S0,r,q,T) == F_target.
    q_implied = r - ln(F_target/S0)/T
    """
    if spot <= 0 or T <= 0 or F_target <= 0:
        return None
    return r - (math.log(F_target / spot) / T)


# -----------------------------
# IPV Engine
# -----------------------------
def run_ipv_check(
    x: EquityForwardIPVInputs,
    tol_abs: float = 0.20,         # currency units
    tol_bps: float = 5.0,          # bps of baseline forward
    tol_q_gap_bps: float = 50.0,   # bps gap between implied and input net carry to trigger hint
    rounding: int = 6
) -> Dict[str, Any]:
    """
    Runs baseline vs market-implied forward checks and returns a compact IPV report.
    Assumes continuous compounding for r and net_carry.
    """
    validate_inputs(x)

    f_baseline = forward_carry(x.spot, x.r, x.net_carry, x.T)

    report: Dict[str, Any] = {
        "status": "N/A (no options provided)",
        "pass_rule": "|ΔF| <= tol_eff (tol_eff = max(tol_abs, tol_bps * F_carry / 10000))",
        "baseline_forward": round(f_baseline, rounding),
        "market_implied_forward": None,
        "abs_spread": None,
        "rel_spread_bps_vs_fbase": None,
        "rel_spread_bps_vs_spot": None,
        "net_carry_input": x.net_carry,
        "net_carry_input_pct": round(x.net_carry * 100, 3),
        "net_carry_implied": None,
        "net_carry_implied_pct": None,
        "net_carry_gap_bps": None,  # (q_impl - q_input) in bps
        "pass_eff": None,
        "tolerances": {
            "tol_abs": tol_abs,
            "tol_bps": tol_bps,
            "tol_eff": None,
            "tol_q_gap_bps": tol_q_gap_bps
        },
        "root_cause_hints": [],
        "assumptions": {
            "compounding": "continuous",
            "net_carry": "dividend_yield - repo/borrow"
        }
    }

    if x.call is None:
        return report

    f_mkt = forward_from_put_call_parity(x.strike, x.call, x.put, x.r, x.T)
    abs_spread = f_mkt - f_baseline

    rel_bps_fbase = (abs_spread / f_baseline) * 10000.0
    rel_bps_spot = (abs_spread / x.spot) * 10000.0

    # Market-standard effective tolerance: looser of absolute and relative thresholds
    tol_eff = max(tol_abs, abs(tol_bps) * f_baseline / 10000.0)

    pass_eff = abs(abs_spread) <= tol_eff
    status = "PASS" if pass_eff else "FAIL"

    q_impl = implied_net_carry(x.spot, f_mkt, x.r, x.T)

    q_gap_bps = None
    if q_impl is not None:
        q_gap_bps = (q_impl - x.net_carry) * 10000.0

    hints: List[str] = []
    if status == "FAIL":
        hints.append("Timestamp alignment (spot vs options).")
        hints.append("Conventions (T, day count, compounding, curve).")

        if abs_spread < 0:
            hints.append("Market-implied forward LOWER: check higher dividends / higher borrow-repo / stale spot.")
        else:
            hints.append("Market-implied forward HIGHER: check lower dividends / lower borrow-repo / stale options.")

        if q_impl is not None:
            if abs(q_gap_bps) >= tol_q_gap_bps:
                hints.append("Dividends / repo-borrow (net carry mismatch).")
        else:
            hints.append("Implied net carry not available (invalid inputs or F<=0).")

        hints.append("Settlement & corporate actions (ex-div, specials, splits).")
        hints.append("Bid/ask consistency (mid vs executable, stale quotes).")

    report.update({
        "status": status,
        "pass_rule": report.get("pass_rule"),
        "baseline_forward": round(f_baseline, rounding),
        "market_implied_forward": round(f_mkt, rounding),
        "abs_spread": round(abs_spread, rounding),
        "rel_spread_bps_vs_fbase": round(rel_bps_fbase, 2),
        "rel_spread_bps_vs_spot": round(rel_bps_spot, 2),
        "net_carry_implied": q_impl,
        "net_carry_implied_pct": (round(q_impl * 100, 3) if q_impl is not None else None),
        "net_carry_gap_bps": (round(q_gap_bps, 1) if q_gap_bps is not None else None),
        "pass_eff": pass_eff,
        "tolerances": {
            **report["tolerances"],
            "tol_eff": tol_eff
        },
        "root_cause_hints": hints
    })

    return report


# -----------------------------
# Output formatting (clean desk-style report)
# -----------------------------
def format_ipv_report(rep: Dict[str, Any], top_hints: int = 3) -> str:
    def fmt_num(v: Optional[float], nd: int) -> str:
        return "N/A" if v is None else f"{v:.{nd}f}"

    t = rep.get("tolerances", {})
    tol_eff = t.get("tol_eff", None)
    tol_abs = t.get("tol_abs", None)
    tol_bps = t.get("tol_bps", None)

    lines: List[str] = []
    lines.append("=" * 40)
    lines.append(" EQUITY FORWARD IPV REPORT")
    lines.append("=" * 40)

    lines.append(f"STATUS            : {rep.get('status', 'N/A')}")
    rule = rep.get("pass_rule")
    if rule:
        lines.append(f"Rule              : {rule}")
    lines.append("")

    lines.append(f"F_baseline (carry): {fmt_num(rep.get('baseline_forward'), 3)}")
    lines.append(f"F_implied (parity): {fmt_num(rep.get('market_implied_forward'), 3)}")
    lines.append("")

    tol_str = "N/A"
    if tol_abs is not None and tol_bps is not None and tol_eff is not None:
        tol_str = f"tol_abs: {tol_abs}, tol_bps: {tol_bps}, tol_eff: {tol_eff:.3f}"
    elif tol_eff is not None:
        tol_str = f"tol_eff: {tol_eff:.3f}"

    spread_abs = rep.get("abs_spread")
    lines.append(f"ΔF (abs)          : {fmt_num(spread_abs, 3)}   ({tol_str})")
    lines.append(f"ΔF (bps vs F)     : {fmt_num(rep.get('rel_spread_bps_vs_fbase'), 2)}")
    lines.append(f"ΔF (bps vs S)     : {fmt_num(rep.get('rel_spread_bps_vs_spot'), 2)}")
    lines.append("")

    lines.append(f"Net carry (input) : {rep.get('net_carry_input_pct', 'N/A')}%")
    lines.append(
        "Net carry (impl.) : "
        + ("N/A" if rep.get("net_carry_implied_pct") is None else f"{rep['net_carry_implied_pct']:.3f}%")
    )

    q_gap_bps = rep.get("net_carry_gap_bps")
    if q_gap_bps is not None:
        sign = "+" if q_gap_bps >= 0 else ""
        lines.append(f"Δq (bps)          : {sign}{q_gap_bps:.1f}")

    hints = rep.get("root_cause_hints", [])
    if hints:
        lines.append("")
        lines.append("Next checks        :")
        for h in hints[:max(0, top_hints)]:
            lines.append(f"- {h}")

    lines.append("=" * 40)
    return "\n".join(lines)


# -----------------------------
# Example run
# -----------------------------
if __name__ == "__main__":
    x = EquityForwardIPVInputs(
        spot=100.0, r=0.03, net_carry=0.01, T=0.5, strike=100.0,
        call=5.20, put=4.80
    )
    rep = run_ipv_check(x, tol_abs=0.20, tol_bps=5.0)
    print(format_ipv_report(rep))
