import math
import json
import numpy as np
import svgwrite
from collections import defaultdict
import fitz  # PyMuPDF

# ---------------------------------------------------
# CONFIGURATION & SETUP
# ---------------------------------------------------
pdf_path = "/mnt/data/SA011 EOS.pdf"  # Path to the PDF file
svg_path = "/mnt/data/SA011_EOS_arrows_black.svg"  # Output SVG file with black arrows
json_path = "/mnt/data/SA011_EOS_arrows.json"  # Output JSON file
crossword_json_path = "/mnt/data/SA011_EOS_crossword_arrows.json"

ANGLE_TOLERANCE = 20  # Tolerance in degrees for detecting a right angle
LONG_ARROW_RATIO = 2.0  # If one leg is at least 2x longer than the other, treat as a long arrow.

# Open the PDF and read the first page.
doc = fitz.open(pdf_path)
page = doc[0]
page_width, page_height = page.rect.width, page.rect.height

# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def shared_point_fixed(seg1, seg2, tol=1e-6):
    for pt1 in seg1:
        for pt2 in seg2:
            if np.allclose(pt1, pt2, atol=tol):
                return pt1
    return None

def angle_between(v1, v2):
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return None
    cosine = np.dot(v1, v2) / (norm1 * norm2)
    cosine = max(min(cosine, 1.0), -1.0)
    return math.degrees(math.acos(cosine))

# ---------------------------------------------------
# EXTRACT LINE SEGMENTS FROM THE PDF DRAWINGS
# ---------------------------------------------------
line_segments = []
for drawing in page.get_drawings():
    for item in drawing["items"]:
        if item[0] == "l":
            seg = (tuple(item[1]), tuple(item[2]))
            line_segments.append(seg)

# Build a mapping from endpoints to segment indices (for fast lookup)
point_to_segments = defaultdict(list)
for i, segment in enumerate(line_segments):
    point_to_segments[segment[0]].append(i)
    point_to_segments[segment[1]].append(i)

# ---------------------------------------------------
# OPTIMIZED ARROW DETECTION (L-SHAPES)
# ---------------------------------------------------
optimized_arrow_data = []
for i, seg1 in enumerate(line_segments):
    for endpoint in seg1:
        for seg2_index in point_to_segments[endpoint]:
            if i >= seg2_index:
                continue
            seg2 = line_segments[seg2_index]
            common = shared_point_fixed(seg1, seg2)
            if common is None:
                continue
            endpoints1 = list(seg1)
            endpoints2 = list(seg2)
            if common in endpoints1:
                endpoints1.remove(common)
            if common in endpoints2:
                endpoints2.remove(common)
            if not endpoints1 or not endpoints2:
                continue
            pt1 = endpoints1[0]
            pt2 = endpoints2[0]
            vec1 = np.array(pt1) - np.array(common)
            vec2 = np.array(pt2) - np.array(common)
            ang = angle_between(vec1, vec2)
            if ang is None or abs(ang - 90) > ANGLE_TOLERANCE:
                continue
            len1 = np.linalg.norm(vec1)
            len2 = np.linalg.norm(vec2)
            if len1 == 0 or len2 == 0:
                continue
            tip, tail = (pt1, pt2) if len1 >= len2 else (pt2, pt1)
            dx, dy = tip[0] - common[0], tip[1] - common[1]
            angle_tip = math.degrees(math.atan2(dy, dx))
            direction = "right" if -45 <= angle_tip < 45 else "up" if 45 <= angle_tip < 135 else "left" if angle_tip >= 135 or angle_tip < -135 else "down"
            optimized_arrow_data.append({
                "common": common,
                "tip": tip,
                "tail": tail,
                "direction": direction
            })

# ---------------------------------------------------
# CONVERT ARROW DATA TO CROSSWORD SYSTEM FORMAT
# ---------------------------------------------------
grid_cols, grid_rows = 23, 26
direction_mapping = {"right": "1", "up": "2", "left": "3", "down": "4"}

def map_to_grid(x, y):
    return max(0, min(int((x / page_width) * grid_cols), grid_cols - 1)), max(0, min(int((y / page_height) * grid_rows), grid_rows - 1))

crossword_json = {"pointers": [], "largePointers": [], "keys": []}
for i, arrow in enumerate(optimized_arrow_data):
    grid_x, grid_y = map_to_grid(arrow["common"][0], arrow["common"][1])
    crossword_json["pointers"].append({
        "type": direction_mapping.get(arrow["direction"], "0"),
        "style": {"z-index": 4, "top": f"{grid_y * 60}px", "left": f"{grid_x * 60}px"},
        "cssClass": "ll lt",
        "position": {"x": grid_x, "y": grid_y}
    })

with open(crossword_json_path, "w") as json_file:
    json.dump(crossword_json, json_file, indent=4)

crossword_json_path
