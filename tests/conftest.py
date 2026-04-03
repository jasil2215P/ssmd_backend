import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/ssmd-test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
