# backend/tests/test_pipeline_isolating.py
import time
from dotenv import load_dotenv
load_dotenv()

from app import jobs, pipeline

TEST_FILE = "../audio/test_freestyle.mp3"

job_id = jobs.create(ext="mp3")
print(f"Created job: {job_id}")

pipeline.start(job_id, TEST_FILE)

seen_stages = []
for _ in range(90):  # up to ~3 min (lalal can take a while)
    job = jobs.get(job_id)
    stage = job["stage"]
    if not seen_stages or seen_stages[-1] != stage:
        seen_stages.append(stage)
        print(f"Stage -> {stage}")
    if stage in ("done", "error"):
        break
    time.sleep(2)

print("\nStage sequence seen:", seen_stages)
print("Final job:", job)

if "isolating" in seen_stages:
    print("'isolating' stage fired")
else:
    print("'isolating' stage never appeared — check pipeline.py")

if job["stage"] == "done":
    print("Pipeline completed successfully")
elif job["stage"] == "error":
    print(f"Pipeline errored: {job['error']}")