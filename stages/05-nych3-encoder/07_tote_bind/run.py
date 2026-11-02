"""S7 Retrieve and bind TOTE templates. Reads only the previous stage output."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "shared"))
from nych3.pipeline import run_stage

if __name__ == "__main__":
    run_stage("07_tote_bind")
    print("07_tote_bind: wrote output/")
