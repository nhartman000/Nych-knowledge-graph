"""S8 Lexical identifiers. Reads only the previous stage output."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "shared"))
from nych3.pipeline import run_stage

if __name__ == "__main__":
    run_stage("08_lexical_ids")
    print("08_lexical_ids: wrote output/")
