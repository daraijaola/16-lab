import os
import time
import requests

LALAL_API_KEY = os.getenv("LALAL_LICENSE_KEY")
URL_API = "https://www.lalal.ai/api"

def isolate_vocals(audio_file_path: str) -> str | None:
    """
    Uploads audio to Lalal.ai, strips the beat,
    and returns a URL to the clean vocals-only stem.
    Returns None if anything fails (fail-safe).
    """
    try:
        filename = os.path.basename(audio_file_path)
        headers = {
            "Authorization": f"license {LALAL_API_KEY}",
            "Content-Disposition": f"attachment; filename={filename}",
        }

        # STEP 1 — Upload
        with open(audio_file_path, "rb") as f:
            upload_resp = requests.post(
                f"{URL_API}/upload/",
                headers=headers,
                data=f,
                timeout=60
            )
        upload_data = upload_resp.json()

        if upload_data.get("status") != "success":
            print(f"[LALAL] Upload failed: {upload_data}")
            return None

        file_id = upload_data["id"]

        # STEP 2 — Split (extract vocals)
        split_resp = requests.post(
            f"{URL_API}/split/",
            headers={"Authorization": f"license {LALAL_API_KEY}"},
            data={"params": f'[{{"id": "{file_id}", "stem": "vocals"}}]'},
            timeout=30
        )
        if split_resp.json().get("status") != "success":
            print(f"[LALAL] Split failed: {split_resp.json()}")
            return None

        # STEP 3 — Poll until done
        for _ in range(24): 
            time.sleep(5)
            check_resp = requests.post(
                f"{URL_API}/check/",
                headers={"Authorization": f"license {LALAL_API_KEY}"},
                data={"id": file_id},
                timeout=30
            )
            result = check_resp.json().get("result", {}).get(file_id, {})
            split_info = result.get("split")

            if split_info:
                return split_info["stem_track"]

            state = result.get("task", {}).get("state")
            if state == "error":
                print(f"[LALAL] Processing error")
                return None

        print("[LALAL] Timeout — job took too long")
        return None

    except Exception as e:
        print(f"[LALAL] Exception: {e}")
        return None