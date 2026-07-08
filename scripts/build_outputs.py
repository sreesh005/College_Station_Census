import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stitch import stitch_county_features
from src.load_sqlite import load_sqlite

stitched = stitch_county_features()
print(stitched[["county_label", "population", "mean_aadt", "general_location_score"]].to_string(index=False))
load_sqlite()
print("sqlite loaded")
