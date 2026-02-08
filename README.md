# Equity Forward IPV Check (Carry vs Put–Call Parity)

A lightweight Python mini-tool for **Valuation Control / IPV** to verify an equity forward price using two independent checks:

1) **Cost-of-carry baseline** (rates + net carry)  
2) **Options-implied forward** via **put–call parity** (call/put with same strike & maturity)

The tool produces a **desk-style report** with a transparent **PASS/FAIL rule**, plus diagnostics (implied net carry and Δq in bps) to speed up break investigation.

---

## What this repo contains

- A small IPV engine to compute:
  - `F_carry` (baseline forward)
  - `F_parity` (market-implied forward from options)
  - `ΔF` in currency and in bps (vs forward baseline and vs spot)
  - `tol_eff` (effective tolerance)
  - `q_impl` (implied net carry) and `Δq (bps)` as a root-cause signal
- A clean, copy-pastable IPV report format.

---

## Method (high level)

**Carry-based forward**
- \( F_{\text{carry}} = S_0 \cdot e^{(r - q)\,T} \)

**Options-implied forward (put–call parity, European framework)**
- \( F_{\text{parity}} = K + e^{rT}\,(C - P) \)

**Difference**
- \( \Delta F = F_{\text{parity}} - F_{\text{carry}} \)

**Effective tolerance**
- `tol_eff = max(tol_abs, tol_bps * F_carry / 10,000)`

**Decision rule**
- PASS if `|ΔF| <= tol_eff`, otherwise FAIL

**Diagnostics**
- Implied net carry `q_impl` that reconciles the carry model with `F_parity`
- `Δq (bps) = (q_impl - q_input) * 10,000`

---

## Quickstart

### Requirements
- Python 3.9+ (no external dependencies)

### Run
Clone the repo and run the script (or paste into a notebook):

```bash
python your_script_name.py
