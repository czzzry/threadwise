from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.local_environment import load_local_environment


load_local_environment(REPO_ROOT)


from src.gmail_companion_ui import main


if __name__ == "__main__":
    raise SystemExit(main())
