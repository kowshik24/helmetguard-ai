from shared.contracts import JobPayload


def test_job_payload() -> None:
    payload = JobPayload(job_id="abc", input_video_uri="data/uploads/x.mp4")
    assert payload.job_id == "abc"
