from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = PROJECT_ROOT / "backend" / "workspace.db"


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class DatabaseIsolationTests(unittest.TestCase):
    def test_standalone_main_import_uses_explicit_temporary_database(self) -> None:
        production_before = sha256(PRODUCTION_DB)
        with tempfile.TemporaryDirectory(prefix="mo-import-isolation-") as temp_dir:
            root = Path(temp_dir)
            isolated_db = root / "isolated.db"
            env = os.environ.copy()
            env["WORKSPACE_ROOT"] = str(root)
            env["WORKSPACE_DATABASE_URL"] = f"sqlite:///{isolated_db.as_posix()}"
            env["PYTHONPATH"] = str(PROJECT_ROOT)
            script = (
                "import json; "
                "from backend import database; "
                "from backend.main import app; "
                "print(json.dumps({'database_url': database.DATABASE_URL, 'db_path': str(database.DB_PATH), 'routes': len(app.routes)}))"
            )
            result = subprocess.run([sys.executable, "-c", script], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(payload["database_url"], env["WORKSPACE_DATABASE_URL"])
            self.assertEqual(payload["db_path"], "None")
            self.assertTrue(isolated_db.exists())
            self.assertGreater(payload["routes"], 50)
        self.assertEqual(sha256(PRODUCTION_DB), production_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
