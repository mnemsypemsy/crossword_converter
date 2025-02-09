import math
import json
import numpy as np
import svgwrite
from collections import defaultdict
import fitz  # PyMuPDF

# ---------------------------------------------------
# CONFIGURATION & SETUP
# ---------------------------------------------------
pdf_path = "/mnt/data/SA011 EOS.pdf"              # Path to your PDF file
svg_path = "/mnt/data/SA011_EOS_arrows_black.svg"  # Output SVG file with black arrows
json_path = "/mnt/data/SA011_EOS_arrows.json"     # Output JSON file

ANGLE_TOLERANCE = 20      # Tolerance in degrees for detecting a right angle
LONG_ARROW_RATIO = 2.0    # If one leg is at least 2x longer than the other, treat as a long arrow.
apply_transform = False   # We do not apply any global transform

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
            if max(len1, len2) / min(len1, len2) >= LONG_ARROW_RATIO:
                if len1 < len2:
                    tip, tail, seg_with_tip, seg_without_tip = pt1, pt2, (common, pt1), (common, pt2)
                else:
                    tip, tail, seg_with_tip, seg_without_tip = pt2, pt1, (common, pt2), (common, pt1)
            else:
                if len1 >= len2:
                    tip, tail, seg_with_tip, seg_without_tip = pt1, pt2, (common, pt1), (common, pt2)
                else:
                    tip, tail, seg_with_tip, seg_without_tip = pt2, pt1, (common, pt2), (common, pt1)
            dx, dy = tip[0] - common[0], tip[1] - common[1]
            angle_tip = math.degrees(math.atan2(dy, dx))
            if -45 <= angle_tip < 45:
                direction = "right"
            elif 45 <= angle_tip < 135:
                direction = "up"
            elif angle_tip >= 135 or angle_tip < -135:
                direction = "left"
            else:
                direction = "down"
            optimized_arrow_data.append({
                "common": common,
                "tip": tip,
                "tail": tail,
                "seg_with_tip": seg_with_tip,
                "seg_without_tip": seg_without_tip,
                "direction": direction
            })

# ---------------------------------------------------
# DRAW ARROWS INTO THE SVG (AFTER PER-ARROW TRANSFORMATION)
# ---------------------------------------------------
dwg = svgwrite.Drawing(svg_path, size=(page_width, page_height))
arrow_marker = dwg.marker(id="arrow", insert=(0, 3), size=(6, 6), orient="auto")
arrow_marker.add(dwg.path(d="M0,0 L0,6 L6,3 Z", fill="black"))
dwg.defs.add(arrow_marker)

arrow_json_data = []

for arrow in optimized_arrow_data:
    common, tip, tail = arrow["common"], arrow["tip"], arrow["tail"]
    center = ((common[0] + tip[0] + tail[0]) / 3, (common[1] + tip[1] + tail[1]) / 3)
    seg_with_tip_trans = arrow["seg_with_tip"]
    seg_without_tip_trans = arrow["seg_without_tip"]
    
    dwg.add(dwg.line(
        start=seg_with_tip_trans[0],
        end=seg_with_tip_trans[1],
        stroke="black",
        stroke_width=2,
        marker_end=arrow_marker.get_funciri()))
    dwg.add(dwg.line(
        start=seg_without_tip_trans[0],
        end=seg_without_tip_trans[1],
        stroke="black",
        stroke_width=2))
    
    arrow_json_data.append({
        "direction": arrow["direction"],
        "common": list(common),
        "tip": list(tip),
        "tail": list(tail),
        "center": [center[0], center[1]]
    })

dwg.save()

with open(json_path, "w") as json_file:
    json.dump(arrow_json_data, json_file, indent=4)

svg_path, json_path
