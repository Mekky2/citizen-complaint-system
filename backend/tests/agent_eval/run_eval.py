"""Measure categorization and severity on complaints_eval.jsonl, separately.

Run from the backend/ folder:
    python -m tests.agent_eval.run_eval                  # keyword baseline, no key needed
    python -m tests.agent_eval.run_eval --llm nim        # Mistral via NIM (needs LLM_API_KEY)
    python -m tests.agent_eval.run_eval --llm-factory pkg.mod:make_llm   # any other LLMClient

Both LLM modes make 2 calls per row (categorize + severity) using the same tools as production.
The labels were written by the project author and are NOT reviewed by municipal staff; some are
debatable. Use the numbers to compare models and find failure patterns, not as certified accuracy.
"""

import argparse
import importlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from app.agents.complaint_agent import rules, tools
from app.agents.complaint_agent.tools import ToolError

DATA = Path(__file__).with_name("complaints_eval.jsonl")
RANK = {"Weak": 0, "Medium": 1, "Critical": 2}


def load_rows() -> list[dict]:
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line]


def baseline_predictors():
    # The keyword baseline has no confidence, so only emergency-wording flags can fire for it.
    return (
        lambda d, a: rules.categorize_rules(d, a),
        lambda d, _c: SimpleNamespace(severity=rules.severity_rules(d), confidence="high"),
    )


def llm_predictors(llm):
    return (
        lambda d, a: tools.categorize(llm, d, a)[0],
        lambda d, c: tools.classify_severity(llm, d, c),
    )


def evaluate(rows: list[dict], predict_cat, predict_sev) -> dict:
    acc = {"category": defaultdict(lambda: [0, 0]), "severity": defaultdict(lambda: [0, 0])}
    confusion, misses = Counter(), []
    errors = under = silent_under = crit_total = crit_hit = 0
    error_reasons: Counter = Counter()
    review_rows = review_flagged = 0
    for r in rows:
        groups = ["ALL", f"lang:{r['language']}", f"tag:{r['tag'] or 'plain'}"]
        try:
            cat = predict_cat(r["description"], r["authority"])
            sev_answer = predict_sev(r["description"], cat)
            sev = sev_answer.severity
            flagged = bool(
                rules.severity_review_notes(r["description"], sev, sev_answer.confidence)
            )
        except ToolError as err:
            errors += 1
            error_reasons[err.reason.value] += 1
            cat = sev = "ERROR"
            flagged = False
        gold_sev = r["expected_severity"]
        for kind, pred, gold in (
            ("category", cat, r["expected_category"]),
            ("severity", sev, gold_sev),
        ):
            for g in groups:
                acc[kind][g][0] += pred == gold
                acc[kind][g][1] += 1
            if pred != gold:
                misses.append((r["id"], kind, gold, pred))
        confusion[(gold_sev, sev)] += 1
        if gold_sev == "Critical":
            crit_total += 1
            crit_hit += sev == "Critical"
        if sev in RANK and RANK[sev] < RANK[gold_sev]:
            under += 1
            silent_under += not flagged
        if r.get("expected_review"):
            review_rows += 1
            review_flagged += flagged
    return {
        "acc": acc,
        "confusion": confusion,
        "misses": misses,
        "errors": errors,
        "error_reasons": error_reasons,
        "under": under,
        "silent_under": silent_under,
        "crit": (crit_hit, crit_total),
        "review": (review_flagged, review_rows),
    }


def report(mode: str, rows: list[dict], res: dict) -> None:
    print(f"mode: {mode} | rows: {len(rows)} | tool errors: {res['errors']}")
    if res["error_reasons"]:
        print(f"  Tool errors by reason: {dict(res['error_reasons'])}")
    for kind in ("category", "severity"):
        print(f"\n{kind.upper()} accuracy")
        for g, (ok, n) in sorted(res["acc"][kind].items()):
            print(f"  {g:<20} {ok:>3}/{n:<3} = {ok / n:.1%}")
        answered = len(rows) - res["errors"]
        if answered and res["errors"]:
            ok_all, _ = res["acc"][kind]["ALL"]
            print(f"  {'(answered only)':<20} {ok_all:>3}/{answered:<3} = {ok_all / answered:.1%}")
    trivial = sum(r["authority"] == r["expected_category"] for r in rows)
    print(
        f"\nReference: 'category = authority' alone scores {trivial}/{len(rows)} "
        f"= {trivial / len(rows):.1%}; the category score must beat this to mean anything."
    )
    hit, total = res["crit"]
    print("\nSAFETY (severity)")
    print(f"  Critical recall:               {hit}/{total} = {hit / total:.1%}")
    print(f"  Under-prioritised (any):       {res['under']}")
    print(f"  ...of which NOT flagged:       {res['silent_under']}  <- the dangerous ones")
    fl, rv = res["review"]
    print(f"  Expected-review rows flagged:  {fl}/{rv}")
    print("\nSeverity confusion (gold -> predicted): count")
    for (gold, pred), n in sorted(res["confusion"].items()):
        print(f"  {gold:<9}-> {pred:<9} {n}")
    print("\nMisses:", *[f"{i}:{k} gold={g} pred={p}" for i, k, g, p in res["misses"]], sep="\n  ")


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--llm", choices=["nim"], help="use the configured NVIDIA NIM model")
    group.add_argument("--llm-factory", help="module:function returning an LLMClient")
    args = ap.parse_args()

    if args.llm == "nim":
        from app.agents.complaint_agent.nim_client import LLMConfigError, build_llm_client

        try:
            predictors, mode = llm_predictors(build_llm_client()), "LLM (NVIDIA NIM)"
        except LLMConfigError as err:
            msg = f"Cannot run --llm nim: {err}. Set LLM_API_KEY in backend/.env."
            raise SystemExit(msg) from err
    elif args.llm_factory:
        module, func = args.llm_factory.split(":")
        llm = getattr(importlib.import_module(module), func)()
        predictors, mode = llm_predictors(llm), f"LLM ({args.llm_factory})"
    else:
        predictors, mode = baseline_predictors(), "keyword baseline"

    rows = load_rows()
    report(mode, rows, evaluate(rows, *predictors))


if __name__ == "__main__":
    main()
