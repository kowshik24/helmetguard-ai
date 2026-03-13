#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalMetrics:
    precision: float
    recall: float
    f1: float
    ocr_accuracy: float | None
    pred_count: int
    gt_count: int
    true_positives: int


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_plate(text: str | None) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text.upper() if ch.isalnum())


def match_violations(pred: list[dict], gt: list[dict], ts_tolerance: float) -> tuple[int, list[tuple[dict, dict]]]:
    used_gt: set[int] = set()
    pairs: list[tuple[dict, dict]] = []
    tp = 0

    for p in pred:
        p_ts = float(p.get("timestamp_sec", 0.0))
        p_no_helmet = int(p.get("no_helmet_count", 0))

        best_idx = None
        best_score = -1.0
        for idx, g in enumerate(gt):
            if idx in used_gt:
                continue
            g_ts = float(g.get("timestamp_sec", 0.0))
            if abs(p_ts - g_ts) > ts_tolerance:
                continue
            g_no_helmet = int(g.get("no_helmet_count", 0))
            score = 1.0 - min(1.0, abs(p_no_helmet - g_no_helmet) / max(1, g_no_helmet))
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is not None:
            used_gt.add(best_idx)
            tp += 1
            pairs.append((p, gt[best_idx]))

    return tp, pairs


def compute_metrics(pred_report: dict, gt_report: dict, ts_tolerance: float) -> EvalMetrics:
    pred = pred_report.get("violations", [])
    gt = gt_report.get("violations", [])

    tp, pairs = match_violations(pred, gt, ts_tolerance)
    pred_count = len(pred)
    gt_count = len(gt)
    fp = max(0, pred_count - tp)
    fn = max(0, gt_count - tp)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    total_ocr = 0
    correct_ocr = 0
    for p, g in pairs:
        gt_plate = normalize_plate(g.get("plate_text"))
        if not gt_plate:
            continue
        pred_plate = normalize_plate(p.get("plate_text"))
        total_ocr += 1
        if pred_plate == gt_plate:
            correct_ocr += 1

    ocr_accuracy = (correct_ocr / total_ocr) if total_ocr else None
    return EvalMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        ocr_accuracy=ocr_accuracy,
        pred_count=pred_count,
        gt_count=gt_count,
        true_positives=tp,
    )


def runtime_summary(report: dict) -> None:
    violations = report.get("violations", [])
    ocr_success = sum(1 for v in violations if v.get("ocr_status") == "success")
    print("Runtime summary")
    print(f"- total_violations: {len(violations)}")
    print(f"- ocr_success_rate: {(ocr_success / len(violations)):.3f}" if violations else "- ocr_success_rate: N/A")
    runtime = report.get("runtime", {})
    if runtime:
        print(f"- detector: {runtime.get('detector')}")
        print(f"- ocr: {runtime.get('ocr')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate HelmetGuard report quality.")
    parser.add_argument("--pred", required=True, help="Path to predicted report JSON")
    parser.add_argument("--gt", required=False, help="Path to ground-truth report JSON")
    parser.add_argument("--ts-tolerance", type=float, default=1.2, help="Timestamp matching tolerance")
    args = parser.parse_args()

    pred_path = Path(args.pred)
    if not pred_path.exists():
        raise SystemExit(f"Prediction report not found: {pred_path}")

    pred_report = load_json(pred_path)
    if not args.gt:
        runtime_summary(pred_report)
        return

    gt_path = Path(args.gt)
    if not gt_path.exists():
        raise SystemExit(f"Ground-truth report not found: {gt_path}")

    gt_report = load_json(gt_path)
    metrics = compute_metrics(pred_report, gt_report, args.ts_tolerance)
    print("Evaluation metrics")
    print(f"- pred_count: {metrics.pred_count}")
    print(f"- gt_count: {metrics.gt_count}")
    print(f"- true_positives: {metrics.true_positives}")
    print(f"- precision: {metrics.precision:.4f}")
    print(f"- recall: {metrics.recall:.4f}")
    print(f"- f1: {metrics.f1:.4f}")
    if metrics.ocr_accuracy is None:
        print("- ocr_accuracy: N/A (no matched GT plates)")
    else:
        print(f"- ocr_accuracy: {metrics.ocr_accuracy:.4f}")


if __name__ == "__main__":
    main()
