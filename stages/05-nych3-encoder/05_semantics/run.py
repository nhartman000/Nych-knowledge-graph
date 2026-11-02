"""S5 Nested semantic structure. Reads only the previous stage output."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "shared"))
from nych3.pipeline import run_stage

if __name__ == "__main__":
    run_stage("05_semantics")
    print("05_semantics: wrote output/")
