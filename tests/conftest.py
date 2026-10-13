import sys
from pathlib import Path
# Make `import splitter` resolve to the packaged implementation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fairshare"))
