"""
Nagy 2020 Skyline Extraction

Reference:
Nagy, B., & Kovács, P. (2020).
"Skyline detection for mountain recognition"

This module implements the connected-components-based skyline extraction
algorithm from Section 3.2 of the paper:
1. Preprocessing: resize, contrast enhance, blue channel, morphological ops
2. Canny edge detection
3. Connected component scoring (size + 2*span)
4. Top-down search on top-3 candidates
5. 1-pixel gap bridging + largest CC selection

Usage as library:
    from replication.nagy_20 import load_image, detect_skyline, draw_skyline

    image = load_image("photo.jpg")
    skyline, scale = detect_skyline(image)
    result = draw_skyline(image, skyline, scale)

Usage as CLI:
    uv run python -m replication.nagy_20 img/IMG_5620.jpeg -o tmp/nagy_edges.jpg
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PIL.ImageOps import exif_transpose

# Paper constants
TARGET_WIDTH = 640        # Paper: 640x480
CLOSING_RADIUS = 5        # Paper: disk r=5
OPENING_RADIUS = 10       # Paper: disk r=10
TOP_K_CANDIDATES = 3      # Paper: top 3 components

# Canny thresholds (reasonable defaults for natural images)
CANNY_LOW = 50
CANNY_HIGH = 150


# --- Image loading (reused from lie_05) ---

def load_image(path: str) -> np.ndarray:
    """Load image with EXIF orientation correction."""
    img = Image.open(path)
    img = exif_transpose(img)
    return np.array(img)


def downscale(image: np.ndarray, target_width: int = TARGET_WIDTH) -> tuple[np.ndarray, float]:
    """
    Downscale image to target width, preserving aspect ratio.

    Returns:
        Tuple of (downscaled image, scale factor)
    """
    height, width = image.shape[:2]
    if width <= target_width:
        return image, 1.0

    scale = target_width / width
    new_height = int(height * scale)

    if len(image.shape) == 3:
        pil_img = Image.fromarray(image)
    else:
        pil_img = Image.fromarray(image, mode='L')

    pil_img = pil_img.resize((target_width, new_height), Image.LANCZOS)
    return np.array(pil_img), scale


# --- Step 1: Preprocessing ---

def adjust_contrast(image: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to enhance contrast.

    Paper doesn't specify contrast method; CLAHE is a reasonable default that
    enhances local contrast without over-amplifying noise.

    Parameters:
        image: RGB image (uint8)
        clip_limit: CLAHE clip limit
        tile_size: CLAHE tile grid size

    Returns:
        Contrast-enhanced RGB image
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)

    # Apply CLAHE to L channel only
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])

    # Convert back to RGB
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def extract_blue_channel(image: np.ndarray) -> np.ndarray:
    """
    Extract blue channel as grayscale.

    From paper: "The sky is in the sharpest contrast to the terrain
    in the blue colour channel"

    Parameters:
        image: RGB image

    Returns:
        Blue channel as grayscale (uint8)
    """
    if len(image.shape) == 2:
        return image
    return image[:, :, 2]  # RGB format, blue is index 2


def morphological_preprocess(
    gray: np.ndarray,
    close_radius: int = CLOSING_RADIUS,
    open_radius: int = OPENING_RADIUS
) -> np.ndarray:
    """
    Apply morphological closing then opening.

    From paper:
    - Closing (disk r=5): removes small holes
    - Opening (disk r=10): removes small foreground objects (tree branches, rocks)

    Parameters:
        gray: Grayscale image (uint8)
        close_radius: Radius for closing structuring element
        open_radius: Radius for opening structuring element

    Returns:
        Preprocessed grayscale image
    """
    # Create disk structuring elements
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * close_radius + 1, 2 * close_radius + 1)
    )
    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * open_radius + 1, 2 * open_radius + 1)
    )

    # Closing: dilate then erode (fills small holes)
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, close_kernel)

    # Opening: erode then dilate (removes small objects)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, open_kernel)

    return opened


# --- Step 1d: Edge detection ---

def detect_edges_canny(
    gray: np.ndarray,
    low_threshold: int = CANNY_LOW,
    high_threshold: int = CANNY_HIGH
) -> np.ndarray:
    """
    Apply Canny edge detection.

    Parameters:
        gray: Grayscale image (uint8)
        low_threshold: Canny low threshold
        high_threshold: Canny high threshold

    Returns:
        Binary edge map (bool)
    """
    edges = cv2.Canny(gray, low_threshold, high_threshold)
    return edges > 0


# --- Step 2: Connected Components ---

def score_component(mask: np.ndarray) -> float:
    """
    Score a connected component: S(C) = μ(C) + 2ρ(C)

    Parameters:
        mask: Binary mask of the component

    Returns:
        Score value
    """
    # μ(C) = pixel count
    size = np.sum(mask)

    # ρ(C) = span (rightmost - leftmost x-coordinate)
    cols = np.where(np.any(mask, axis=0))[0]
    if len(cols) == 0:
        return 0.0
    span = cols[-1] - cols[0]

    return float(size + 2 * span)


def find_top_candidates(
    edge_map: np.ndarray,
    k: int = TOP_K_CANDIDATES
) -> tuple[list[np.ndarray], np.ndarray]:
    """
    Find top-k connected components by score.

    Parameters:
        edge_map: Binary edge map
        k: Number of top candidates to return

    Returns:
        Tuple of (list of component masks, labeled image)
    """
    # Find 8-connected components
    edge_uint8 = edge_map.astype(np.uint8) * 255
    num_labels, labels = cv2.connectedComponents(edge_uint8, connectivity=8)

    # Score each component (skip background label 0)
    scores = []
    for label in range(1, num_labels):
        mask = labels == label
        score = score_component(mask)
        scores.append((score, label, mask))

    # Sort by score descending
    scores.sort(key=lambda x: x[0], reverse=True)

    # Return top k
    top_masks = [item[2] for item in scores[:k]]

    return top_masks, labels


# --- Step 3: Top-Down Search ---

def topdown_search(candidate_masks: list[np.ndarray], width: int, height: int) -> np.ndarray:
    """
    For each column, find the topmost pixel belonging to any candidate.

    Parameters:
        candidate_masks: List of binary masks for top candidates
        width: Image width
        height: Image height

    Returns:
        Skyline as array of row indices (length = width), -1 for gaps
    """
    # Combine all candidate masks
    combined = np.zeros((height, width), dtype=bool)
    for mask in candidate_masks:
        combined |= mask

    # For each column, find topmost pixel
    skyline = np.full(width, -1, dtype=np.int32)
    for col in range(width):
        rows = np.where(combined[:, col])[0]
        if len(rows) > 0:
            skyline[col] = rows[0]  # topmost = smallest row index

    return skyline


# --- Step 4: Bridge 1-Pixel Gaps ---

def bridge_one_pixel_gaps(skyline: np.ndarray) -> np.ndarray:
    """
    Fill single-column gaps by linear interpolation.

    Parameters:
        skyline: Row indices array with -1 for gaps

    Returns:
        Skyline with 1-pixel gaps filled
    """
    result = skyline.copy()
    N = len(result)

    for col in range(1, N - 1):
        if result[col] == -1 and result[col - 1] >= 0 and result[col + 1] >= 0:
            # Linear interpolation (average of neighbors)
            result[col] = (result[col - 1] + result[col + 1]) // 2

    return result


# --- Step 5: Second CC Analysis ---

def select_largest_component(skyline: np.ndarray) -> np.ndarray:
    """
    Run CC labeling on skyline and select the largest connected component.

    A connected component in the skyline is a contiguous run of valid (non -1) values.

    Parameters:
        skyline: Row indices array with -1 for gaps

    Returns:
        Skyline with only the largest connected segment, others set to -1
    """
    N = len(skyline)
    result = np.full(N, -1, dtype=np.int32)

    # Find connected segments (runs of valid values)
    segments = []
    start = None

    for col in range(N):
        if skyline[col] >= 0:
            if start is None:
                start = col
        else:
            if start is not None:
                segments.append((start, col))
                start = None

    # Don't forget last segment
    if start is not None:
        segments.append((start, N))

    if not segments:
        return result

    # Find largest segment by length
    largest = max(segments, key=lambda x: x[1] - x[0])

    # Copy only the largest segment
    start, end = largest
    result[start:end] = skyline[start:end]

    return result


# --- High-level API ---

def preprocess(
    image: np.ndarray,
    close_radius: int = CLOSING_RADIUS,
    open_radius: int = OPENING_RADIUS
) -> np.ndarray:
    """
    Full preprocessing pipeline (Steps 1a-1c).

    Parameters:
        image: RGB image
        close_radius: Morphological closing radius
        open_radius: Morphological opening radius

    Returns:
        Preprocessed grayscale image
    """
    # Step 1a: Adjust contrast
    contrasted = adjust_contrast(image)

    # Step 1b: Extract blue channel
    blue = extract_blue_channel(contrasted)

    # Step 1c: Morphological operations
    preprocessed = morphological_preprocess(blue, close_radius, open_radius)

    return preprocessed


def detect_skyline(
    image: np.ndarray,
    target_width: int = TARGET_WIDTH,
    close_radius: int = CLOSING_RADIUS,
    open_radius: int = OPENING_RADIUS,
    canny_low: int = CANNY_LOW,
    canny_high: int = CANNY_HIGH,
    top_k: int = TOP_K_CANDIDATES
) -> tuple[np.ndarray, float]:
    """
    High-level skyline detection API.

    Implements the full Nagy 2020 algorithm.

    Parameters:
        image: Input image (RGB)
        target_width: Width to downscale to
        close_radius: Morphological closing radius
        open_radius: Morphological opening radius
        canny_low: Canny low threshold
        canny_high: Canny high threshold
        top_k: Number of top CC candidates to consider

    Returns:
        Tuple of (skyline row indices at target_width scale, scale factor)
    """
    # Downscale
    image_small, scale = downscale(image, target_width)
    height, width = image_small.shape[:2]

    # Step 1: Preprocessing
    preprocessed = preprocess(image_small, close_radius, open_radius)

    # Step 1d: Canny edge detection
    edge_map = detect_edges_canny(preprocessed, canny_low, canny_high)

    # Step 2: Find top-k candidates by CC scoring
    candidates, _ = find_top_candidates(edge_map, k=top_k)

    if not candidates:
        # No edges found
        return np.full(width, -1, dtype=np.int32), scale

    # Step 3: Top-down search
    skyline = topdown_search(candidates, width, height)

    # Step 4: Bridge 1-pixel gaps
    skyline = bridge_one_pixel_gaps(skyline)

    # Step 5: Select largest connected component
    skyline = select_largest_component(skyline)

    return skyline, scale


def draw_skyline(
    image: np.ndarray,
    skyline: np.ndarray,
    scale: float = 1.0,
    color: tuple = (0, 255, 0),
    thickness: int = 2
) -> np.ndarray:
    """
    Draw skyline on image.

    Parameters:
        image: RGB image to draw on
        skyline: Row indices at processing scale
        scale: Scale factor from original to processing size
        color: RGB color for skyline
        thickness: Line thickness

    Returns:
        Image with skyline drawn
    """
    result = image.copy()
    N = len(skyline)

    for col in range(N - 1):
        if skyline[col] < 0 or skyline[col + 1] < 0:
            continue

        # Scale back to original image coordinates
        x1 = int(col / scale)
        y1 = int(skyline[col] / scale)
        x2 = int((col + 1) / scale)
        y2 = int(skyline[col + 1] / scale)

        cv2.line(result, (x1, y1), (x2, y2), color, thickness)

    return result


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Nagy 2020 Skyline Extraction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("image", help="Input image path")
    parser.add_argument("-o", "--output", default="tmp/nagy_output.jpg",
                        help="Output path for skyline overlay")
    parser.add_argument("--target-width", type=int, default=TARGET_WIDTH,
                        help="Width to downscale to (640 = paper resolution)")

    # Preprocessing options
    parser.add_argument("--close-radius", type=int, default=CLOSING_RADIUS,
                        help="Morphological closing radius")
    parser.add_argument("--open-radius", type=int, default=OPENING_RADIUS,
                        help="Morphological opening radius")

    # Edge detection options
    parser.add_argument("--canny-low", type=int, default=CANNY_LOW,
                        help="Canny low threshold")
    parser.add_argument("--canny-high", type=int, default=CANNY_HIGH,
                        help="Canny high threshold")

    # CC options
    parser.add_argument("--top-k", type=int, default=TOP_K_CANDIDATES,
                        help="Number of top CC candidates")

    # Debug options
    parser.add_argument("--save-edges", help="Save edge map to this path")
    parser.add_argument("--save-preprocessed", help="Save preprocessed image to this path")
    parser.add_argument("--save-candidates", help="Save candidate visualization to this path")

    args = parser.parse_args()

    # Load image with EXIF orientation
    print(f"Loading {args.image}...")
    image = load_image(args.image)
    orig_height, orig_width = image.shape[:2]
    print(f"Original size: {orig_width} x {orig_height}")

    # Downscale for processing
    image_small, scale = downscale(image, args.target_width)
    proc_height, proc_width = image_small.shape[:2]
    print(f"Processing size: {proc_width} x {proc_height} (scale={scale:.4f})")

    # Step 1: Preprocessing
    print(f"Preprocessing (close_r={args.close_radius}, open_r={args.open_radius})...")
    preprocessed = preprocess(image_small, args.close_radius, args.open_radius)

    if args.save_preprocessed:
        Path(args.save_preprocessed).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(preprocessed).save(args.save_preprocessed)
        print(f"Saved preprocessed image to {args.save_preprocessed}")

    # Step 1d: Canny edge detection
    print(f"Edge detection (Canny {args.canny_low}/{args.canny_high})...")
    edge_map = detect_edges_canny(preprocessed, args.canny_low, args.canny_high)
    edge_count = np.sum(edge_map)
    print(f"Edge pixels: {edge_count} ({100*edge_count/edge_map.size:.1f}%)")

    if args.save_edges:
        Path(args.save_edges).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((edge_map.astype(np.uint8) * 255)).save(args.save_edges)
        print(f"Saved edge map to {args.save_edges}")

    # Step 2: Find top-k candidates
    print(f"Finding top {args.top_k} connected components...")
    candidates, labels = find_top_candidates(edge_map, k=args.top_k)
    print(f"Found {len(candidates)} candidates")

    for i, mask in enumerate(candidates):
        score = score_component(mask)
        size = np.sum(mask)
        cols = np.where(np.any(mask, axis=0))[0]
        span = cols[-1] - cols[0] if len(cols) > 0 else 0
        print(f"  Candidate {i+1}: size={size}, span={span}, score={score:.0f}")

    if args.save_candidates:
        # Visualize candidates in different colors
        vis = np.zeros((proc_height, proc_width, 3), dtype=np.uint8)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        for i, mask in enumerate(candidates[:3]):
            vis[mask] = colors[i % len(colors)]
        Path(args.save_candidates).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(vis).save(args.save_candidates)
        print(f"Saved candidate visualization to {args.save_candidates}")

    if not candidates:
        print("WARNING: No candidates found!")
        return 1

    # Step 3: Top-down search
    print("Running top-down search...")
    skyline = topdown_search(candidates, proc_width, proc_height)
    valid_before = np.sum(skyline >= 0)
    print(f"Initial skyline: {valid_before}/{proc_width} columns ({100*valid_before/proc_width:.1f}%)")

    # Step 4: Bridge 1-pixel gaps
    skyline = bridge_one_pixel_gaps(skyline)
    valid_after_bridge = np.sum(skyline >= 0)
    print(f"After bridging: {valid_after_bridge}/{proc_width} columns")

    # Step 5: Select largest connected component
    skyline = select_largest_component(skyline)
    valid_final = np.sum(skyline >= 0)
    print(f"Final skyline: {valid_final}/{proc_width} columns ({100*valid_final/proc_width:.1f}%)")

    if valid_final > 0:
        min_row = np.min(skyline[skyline >= 0])
        max_row = np.max(skyline[skyline >= 0])
        print(f"Skyline row range: {min_row} - {max_row}")

        # Draw skyline on original image
        skyline_img = draw_skyline(image, skyline, scale, color=(0, 255, 0), thickness=4)

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(skyline_img).save(str(output_path))
        print(f"Saved skyline overlay to {output_path}")

        # Save CSV for debugging
        csv_path = output_path.with_suffix(".csv")
        with open(csv_path, "w") as f:
            f.write("col,row,row_orig\n")
            for col in range(len(skyline)):
                row = skyline[col]
                row_orig = int(row / scale) if row >= 0 else -1
                f.write(f"{col},{row},{row_orig}\n")
        print(f"Saved skyline CSV to {csv_path}")
    else:
        print("WARNING: No valid skyline path found!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
