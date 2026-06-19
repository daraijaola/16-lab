from dotenv import load_dotenv
load_dotenv()

from app.lalal_helper import isolate_vocals


TEST_FILE = "../audio/test_freestyle.mp3"

print("Sending to lalal.ai...")
result = isolate_vocals(TEST_FILE)

if result:
    print(f"Success — clean vocal stem URL:\n{result}")
else:
    print("Failed or timed out — check console output above for the reason")