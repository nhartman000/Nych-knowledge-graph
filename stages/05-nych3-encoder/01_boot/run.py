"""S1 Load boot instructions. Reads only the previous stage output."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "shared"))
from nych3.pipeline import run_stage

if __name__ == "__main__":
    run_stage("01_boot")
    print("01_boot: wrote output/")
