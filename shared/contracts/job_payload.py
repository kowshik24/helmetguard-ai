from pydantic import BaseModel


class JobPayload(BaseModel):
    job_id: str
    input_video_uri: str
