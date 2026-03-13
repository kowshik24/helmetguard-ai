from scripts.benchmark import compute_metrics


def test_compute_metrics_basic() -> None:
    pred = {
        "violations": [
            {"timestamp_sec": 10.0, "no_helmet_count": 1, "plate_text": "DHAKA1234"},
            {"timestamp_sec": 30.0, "no_helmet_count": 2, "plate_text": None},
        ]
    }
    gt = {
        "violations": [
            {"timestamp_sec": 10.5, "no_helmet_count": 1, "plate_text": "DHAKA1234"},
            {"timestamp_sec": 55.0, "no_helmet_count": 1, "plate_text": "XYZ77"},
        ]
    }

    metrics = compute_metrics(pred, gt, ts_tolerance=1.0)
    assert metrics.true_positives == 1
    assert metrics.pred_count == 2
    assert metrics.gt_count == 2
    assert round(metrics.precision, 4) == 0.5
    assert round(metrics.recall, 4) == 0.5
    assert round(metrics.f1, 4) == 0.5
    assert metrics.ocr_accuracy == 1.0
