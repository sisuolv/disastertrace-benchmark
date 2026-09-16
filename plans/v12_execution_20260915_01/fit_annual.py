"""Frozen two-bank annual fit with chronological dynamic-source purging."""
import argparse
import datetime as dt
import importlib.util
import itertools
import json
import pickle
import shutil
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.native_feature import validate_feature_bank
from disastertrace.monitoring_v1.providers.versions import current_taf
from disastertrace.monitoring_v1.regional_calibration_v2 import fit_fixed_prior
from disastertrace.monitoring_v1.native_feature_forecast import predict_features
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import utc_us, canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
OUT = RUN / "annual_stage_B/fit"
MODES = ("common", "values")


def helper():
    spec = importlib.util.spec_from_file_location("frozen_feature_math", OUT / "source/fit_native_feature_bank.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def prepare():
    OUT.mkdir(exist_ok=False)
    (OUT / "source").mkdir()
    shutil.copy2(REPO / "plans/v10_execution_20260914_01/scripts/fit_native_feature_bank.py", OUT / "source/fit_native_feature_bank.py")
    publish(OUT / "REGISTRATION.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "modes": list(MODES),
        "fit_interval": ["2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z"],
        "calibration_interval": ["2024-01-01T00:00:00Z", "2024-12-01T00:00:00Z"],
        "excluded_previously_used_calendar": "2024-12; retained source QA only, excluded from this new fit/calibration",
        "calibration_exposure": "2024-02 native source QA was previously performed; historical exposure outside recorded manifests remains unknown; no claim of an unseen confirmatory calibration set",
        "internal_selection": "none; fixed existing L2=1, prior mass=2; no hyperparameter search",
        "primary": "raw coherent three-class softmax", "secondary": "PAV prior2 then coherent CDF",
        "fit_weights": "one unit total weight per station/target window across all lawful disclosure subsets",
        "clock": "existing native feature training convention at cutoff minus600s; application forecasts use registered actual public slots",
        "role_footprint": "query observation windows, target reference window, all currently selected native version issue/valid intervals; static schemas excluded",
        "dynamic_versions_disjoint_across_roles": True, "all72_native_joins_required": True,
        "new_model_calls": 0, "confirmation_opened": False,
        "files": {str(p): digest(p) for p in [Path(__file__), OUT / "source/fit_native_feature_bank.py"]},
        "source_tree": {str(p): digest(p) for p in (RUN / "branch_source/disastertrace").rglob("*.py")}})


def feature_month(row):
    dataset = Path(row["dataset"])
    folder = OUT / "features" / row["unit"]; folder.mkdir(exist_ok=False)
    math_module = helper()
    reg = read(OUT / "REGISTRATION.json")
    bounds = {role: tuple(utc_us(t) for t in reg[key]) for role,key in
        (("fit", "fit_interval"), ("calibration", "calibration_interval"))}
    targets = {r["target_id"]: r for r in read(dataset / "public/TARGETS.json")}
    opportunities = read(dataset / "public/OPPORTUNITIES.json")
    pairs = {r["opportunity_id"]: r for r in read(dataset / "public/E_F_PAIRS.json")}
    outcomes = {r["target_id"]: r for r in read(dataset / "private/OUTCOMES.json")}
    queries = {r["query_id"]: r for r in read(dataset / "public/QUERY_CATALOG.json")}
    products = read(dataset / "environment/NATIVE_PRODUCT_INDEX.json")
    by_source = {r["source_id"]: r for r in products}
    rows, footprints = [], []
    for opportunity in opportunities:
        oid = opportunity["opportunity_id"]; target = targets[opportunity["target_id"]]
        at = opportunity["cutoff"] - 600_000_000
        decision = current_taf(products, station=target["entity"], cutoff=at,
            start=target["physical_start"], end=target["physical_end"])
        native = [by_source[sid] for sid in decision["source_ids"]]
        qids = pairs[oid]["query_ids"]
        lower = min([queries[q]["slot_start"] for q in qids] + [target["physical_start"]] + [p["issued_at"] for p in native])
        upper = max([target["physical_end"]] + [queries[q]["slot_end"] for q in qids] + [p["valid_end"] for p in native if p.get("valid_end") is not None])
        eligible = [name for name,(lo,hi) in bounds.items() if lo<=lower and upper<=hi]
        role = eligible[0] if len(eligible)==1 else "purged"
        versions = [p["source_id"] for p in native] + qids + ["reference:" + target["target_id"]]
        footprints.append({"opportunity_id": oid, "role": role, "footprint_start": lower,
            "footprint_end": upper, "native_versions": versions, "outcome": outcomes[target["target_id"]]["outcome"]})
        if role != "purged":
            rows.append({**opportunity, "dataset": str(dataset), "region": row["unit"].split("__")[0],
                "station": target["entity"], "role": role, "query_ids": qids,
                "outcome": outcomes[target["target_id"]]["outcome"]})
    examples = list(math_module.native_examples(dataset, rows))
    packed = {}
    for role in bounds:
        usable = [r for r in examples if r["role"]==role and r["class"] is not None]
        packed[role] = {mode: math_module.vectors(usable, mode) for mode in MODES}
    path = folder / "features.pkl"
    with path.open("xb") as f:
        pickle.dump(packed, f, protocol=5)
    publish(folder / "FOOTPRINTS.json", footprints)
    result = {"unit": row["unit"], "feature_file": str(path), "feature_sha256": digest(path),
        "footprints_file": str(folder / "FOOTPRINTS.json"), "footprints_sha256": digest(folder / "FOOTPRINTS.json"),
        "registered": len(opportunities), "roles": dict(Counter(r["role"] for r in footprints)),
        "missing_labeled_opportunities": sum(r["outcome"] is None for r in footprints),
        "usable_information_units": len([r for r in examples if r["class"] is not None])}
    publish(folder / "RESULT.json", result)
    print(json.dumps(result), flush=True)
    return result


def execute(workers):
    reg = read(OUT / "REGISTRATION.json")
    for name, sha in {**reg["files"], **reg["source_tree"]}.items():
        if digest(Path(name)) != sha:
            raise ValueError("Annual bank implementation changed")
    publish(OUT / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "workers": workers})
    until = dt.datetime.fromisoformat("2026-09-16T00:24:27+00:00").timestamp()
    joins_path = RUN / "annual_stage_B/joins/RESULT.json"
    while not joins_path.exists():
        if time.time()>=until:
            publish(OUT / "RESULT.json", {"passed": False, "status": "join_not_complete_before_fit_deadline"})
            return
        time.sleep(60)
    joins = read(joins_path)
    if not joins.get("passed"):
        publish(OUT / "RESULT.json", {"passed": False, "status": "blocked_by_unqualified_annual_join", "join_sha256": digest(joins_path)})
        return
    (OUT / "features").mkdir()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(feature_month, joins["results"]))
    roles = {"fit": defaultdict(list), "calibration": defaultdict(list)}
    version_roles = {}
    role_counts, labels = Counter(), Counter()
    for result in results:
        if digest(Path(result["feature_file"])) != result["feature_sha256"] or digest(Path(result["footprints_file"])) != result["footprints_sha256"]:
            raise ValueError("Frozen extracted features changed")
        for row in read(Path(result["footprints_file"])):
            role = row["role"]; role_counts[role] += 1; labels[(role, str(row["outcome"]))] += 1
            if role == "purged": continue
            for version in row["native_versions"]:
                if version_roles.setdefault(version, role) != role:
                    raise ValueError("A dynamic version crosses annual roles")
        with Path(result["feature_file"]).open("rb") as f:
            packed = pickle.load(f)
        for role in roles:
            for mode in MODES:
                roles[role][mode].extend(packed[role][mode])
    publish(OUT / "ROLE_ADMISSION.json", {"passed": True, "footprint_counts": dict(role_counts),
        "labels": {str(k):v for k,v in labels.items()}, "dynamic_versions_checked": len(version_roles),
        "cross_role_dynamic_versions": 0, "unseen_confirmation_claim": False, "feature_results": results})
    math_module = helper()
    for mode in MODES:
        bank = math_module.fit(roles["fit"][mode], mode)
        bank["mapping_version"] = "pooled_2023_annual_softmax_" + mode + ".v1"
        observations = defaultdict(list)
        for features, label, weight, _ in roles["calibration"][mode]:
            probability = predict_features(bank, features)
            for threshold, y in ((1000,int(label==0)), (5000,int(label<2))):
                observations[str(threshold)].append((probability[str(threshold)], y, weight))
        bank["post_calibration"] = {t: fit_fixed_prior(rows, prior_mass=2) for t,rows in observations.items()}
        validate_feature_bank(bank, calibrated=False); validate_feature_bank(bank, calibrated=True)
        publish(OUT / ("BANK_" + mode + ".json"), bank)
    publish(OUT / "BANK_FREEZE.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "banks": {mode:digest(OUT / ("BANK_"+mode+".json")) for mode in MODES},
        "role_admission_sha256": digest(OUT / "ROLE_ADMISSION.json"), "registration_sha256": digest(OUT / "REGISTRATION.json"),
        "new_2025_evaluation_before_freeze": False, "confirmation_opened": False})
    publish(OUT / "RESULT.json", {"passed": True, "status": "annual_raw_and_calibrated_banks_frozen",
        "banks": list(MODES), "annual_native_joins": 72, "new_model_calls": 0,
        "calibration_months": 11, "fit_year": 2023, "confirmation_opened": False,
        "scientific_comparison_complete": False, "loss_comparison_required": True})


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("mode", choices=["prepare","execute"])
    parser.add_argument("--workers", type=int, default=12); args=parser.parse_args()
    prepare() if args.mode=="prepare" else execute(args.workers)
