"""Point junk_cleaner at a throwaway workspace before any test imports it."""
import json, os, sys, tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_workdir = Path(tempfile.mkdtemp(prefix="junk-cleaner-test-"))
_example = json.loads((REPO_ROOT / "config.json.example").read_text())
_example["microsoft_graph"]["junk_folder_id"] = "test-folder-id"
(_workdir / "config.json").write_text(json.dumps(_example))
os.environ["JUNK_CLEANER_HOME"] = str(_workdir)
