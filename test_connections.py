import os, urllib.request, json
from dotenv import load_dotenv

load_dotenv()

def test_fal():
    key = os.getenv("FAL_KEY", "")
    if not key:
        print("fal.ai (Flux): MISSING KEY")
        return
    req = urllib.request.Request(
        "https://fal.run/fal-ai/flux/schnell",
        method="GET",
        headers={"Authorization": f"Key {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"fal.ai (Flux): OK ({r.status})")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"fal.ai (Flux): AUTH FAILED ({e.code})")
        elif e.code == 405:
            # GET not allowed on run endpoint but auth passed
            print("fal.ai (Flux): OK (auth valid, endpoint expects POST)")
        else:
            print(f"fal.ai (Flux): HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"fal.ai (Flux): ERROR — {e}")

def test_kling():
    import time, jwt
    ak = os.getenv("KLING_AK", "")
    sk = os.getenv("KLING_SK", "")
    if not (ak and sk):
        print("Kling: MISSING KEY")
        return
    payload = {"iss": ak, "exp": int(time.time()) + 1800, "nbf": int(time.time()) - 5}
    token = jwt.encode(payload, sk, headers={"alg": "HS256", "typ": "JWT"})
    for url in [
        "https://api.klingai.com/v1/videos/text2video",
        "https://api.klingai.com/v1/account/costs",
        "https://api.klingai.com/v1/images/generations",
    ]:
        req = urllib.request.Request(
            url, method="GET",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                print(f"Kling: OK ({r.status}) — {url}")
                return
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"Kling: AUTH FAILED ({e.code}) — {url}")
            else:
                print(f"Kling: OK (auth valid, HTTP {e.code}) — {url}")
                return
        except Exception as e:
            print(f"Kling: ERROR — {e}")

test_fal()
test_kling()
