import os
import json
from typing import List, Tuple, Optional, Dict
from PIL import Image
import numpy as np

class WindowSelector:
    """Minimal window region selector used by IntelligentMonitor."""

    def __init__(self):
        self.ocr_reader = None

    def set_ocr_reader(self, reader) -> None:
        self.ocr_reader = reader

    # Utilities for loading and saving configuration
    def _load_config(self) -> Dict:
        if os.path.exists("window_regions.json"):
            try:
                with open("window_regions.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_config(self, data: Dict) -> None:
        with open("window_regions.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def select_chat_region(self) -> Optional[List[Tuple[int, int, int, int]]]:
        """Load saved chat regions from configuration."""
        data = self._load_config()
        if not data:
            return None
        first = next(iter(data.values()))
        regions = []
        if "regions" in first:
            for r in first["regions"]:
                regions.append((r["x"], r["y"], r["width"], r["height"]))
        elif "region" in first:
            r = first["region"]
            regions.append((r["x"], r["y"], r["width"], r["height"]))
        elif {"x", "y", "width", "height"}.issubset(first):
            regions.append((first["x"], first["y"], first["width"], first["height"]))
        return regions if regions else None

    def select_chat_region_for_window(self, window_info: Dict) -> Dict:
        """Placeholder for interactive region selection.
        Here we simply return any saved configuration if available."""
        regions = self.select_chat_region() or []
        return {"regions": regions, "input_box": None, "window": window_info}

    def save_region(self, name: str, region: Tuple[int, int, int, int]) -> None:
        data = self._load_config()
        data[name] = {
            "region": {
                "x": region[0],
                "y": region[1],
                "width": region[2],
                "height": region[3],
            }
        }
        self._save_config(data)

    def save_regions(self, name: str, regions: List[Tuple[int, int, int, int]]) -> None:
        data = self._load_config()
        data[name] = {
            "regions": [
                {"x": r[0], "y": r[1], "width": r[2], "height": r[3]} for r in regions
            ]
        }
        self._save_config(data)

    def save_regions_with_window_info(
        self, name: str, regions: List[Tuple[int, int, int, int]], window_info: Dict
    ) -> None:
        data = self._load_config()
        data[name] = {
            "window": window_info,
            "regions": [
                {"x": r[0], "y": r[1], "width": r[2], "height": r[3]} for r in regions
            ],
        }
        self._save_config(data)

    def extract_region_text(
        self,
        image: Image.Image,
        region: Tuple[int, int, int, int],
        ocr_reader=None,
    ) -> str:
        """Extract text from the specified region using the available OCR reader."""
        reader = ocr_reader or self.ocr_reader
        if reader is None:
            return ""
        x, y, w, h = region
        try:
            crop = image.crop((x, y, x + w, y + h))
            result = reader.readtext(np.array(crop))
            return " ".join(r[1] for r in result)
        except Exception:
            return ""
