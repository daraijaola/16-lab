import os

os.environ["LALAL_LICENSE_KEY"] = "invalid_key_on_purpose"

from app.lalal_helper import isolate_vocals

TEST_FILE = "../audio/test_freestyle.mp3" 

print("Sending to lalal.ai with a BROKEN key (expecting failure)...")
result = isolate_vocals(TEST_FILE)

print("Result:", result)

if result is None:
    print("Fail-safe works — isolate_vocals() returned None instead of crashing")
else:
    print("Something's wrong — expected None but got a URL")