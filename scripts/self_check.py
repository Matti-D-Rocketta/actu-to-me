# scripts/self_check.py — vérifs rapides
import sys, importlib.util, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
OUT = ROOT / "out"

def mod_ok(m:str)->bool:
    return importlib.util.find_spec(m) is not None

def main():
    report = {
        "python": sys.executable,
        "env_exists": ENV.exists(),
        "out_exists": OUT.exists(),
        "modules": {m: mod_ok(m) for m in ["openai","feedparser","yaml","dotenv","readability","bs4","lxml","requests","newspaper"]}
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
