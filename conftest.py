# conftest.py  (create this in your project ROOT)
# This file tells pytest to add src/ to the Python path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))