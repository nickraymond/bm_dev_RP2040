# /lib/bm_store.py
import os, json

def ensure_dir(path: str):
    """Create /config, /logs, etc. (idempotent)."""
    if not path or path == "/":
        return
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            os.listdir(cur)  # exists
        except Exception as e:
            try:
                os.mkdir(cur)
                print(f"[bm_store] mkdir {cur}")
            except Exception as e2:
                print(f"[bm_store] ERROR mkdir {cur}: {e2}")

def read_json(path: str, defaults: dict):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[bm_store] read_json fallback -> defaults ({e})")
        return dict(defaults)

def write_json_atomic(path: str, obj: dict) -> bool:
    """Write to path atomically. Returns True/False."""
    d = path.rsplit("/", 1)[0] or "/"
    ensure_dir(d)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f)
            f.flush()
        os.rename(tmp, path)
        print(f"[bm_store] wrote {path}")
        return True
    except Exception as e:
        print(f"[bm_store] ERROR write {path}: {e}")
        try:
            # cleanup tmp if present
            os.remove(tmp)
        except Exception:
            pass
        return False
