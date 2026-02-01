"""
Lie 2005 Skyline Detection

Reference:
Lie, W-N., Lin, T.C-I., Lin, T-C., & Hung, K-S. (2005).
"A robust dynamic programming algorithm to extract skyline in images for navigation."

This module implements:
1. Preprocessing: EXIF correction, downscaling, Sobel+Otsu edge detection
2. DP skyline search with gap tolerance (paper §3)

TODO: Switch to 2x resolution (704px) with ksize=5

Usage as library:
    from replication.lie_05 import load_image, downscale, detect_edges, detect_skyline

    image = load_image("photo.jpg")  # EXIF-corrected
    image_small, scale = downscale(image, 352)
    edge_map, magnitude = detect_edges(image_small)
    skyline, _ = detect_skyline(image)

Usage as CLI:
    uv run python -m replication.lie_05 img/IMG_5620.jpeg -o output/edges.jpg --run-dp
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PIL.ImageOps import exif_transpose
from skimage.filters import threshold_otsu

# Original paper resolution (352x240)
# TODO: Switch to 2x (704px) for better precision, with ksize=5
TARGET_WIDTH = 352
DEFAULT_KSIZE = 3

# DP algorithm parameters (paper defaults for 352x240)
DEFAULT_DELTA = 3    # max vertical jump per column
DEFAULT_TOG = 30     # gap tolerance (columns)
# Paper uses pun=100, but this allows the entry cost (i+1)² to pull the skyline
# above actual edges via gap bridging. pun=500 makes bridging expensive enough
# that the algorithm prefers entering at actual edge positions.
DEFAULT_PUN = 500.0  # penalty per dummy link


# --- Image loading ---

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


# --- Edge detection ---

def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert RGB image to grayscale luminance."""
    if len(image.shape) == 2:
        return image.astype(np.float64)
    return (
        0.299 * image[:, :, 0] +
        0.587 * image[:, :, 1] +
        0.114 * image[:, :, 2]
    ).astype(np.float64)


def sobel_edges(image: np.ndarray, ksize: int = DEFAULT_KSIZE) -> np.ndarray:
    """
    Apply Sobel edge detection to image.

    Parameters:
        image: Grayscale or RGB image
        ksize: Sobel kernel size (3 for 352px, 5 for 704px)

    Returns:
        Edge magnitude normalized to [0, 255]
    """
    gray = to_grayscale(image)

    # Ensure uint8 for cv2
    if gray.max() > 1:
        gray_u8 = gray.astype(np.uint8)
    else:
        gray_u8 = (gray * 255).astype(np.uint8)

    # Sobel with specified kernel size
    sobel_x = cv2.Sobel(gray_u8, cv2.CV_64F, 1, 0, ksize=ksize)
    sobel_y = cv2.Sobel(gray_u8, cv2.CV_64F, 0, 1, ksize=ksize)

    # Magnitude
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

    # Normalize to [0, 255]
    if magnitude.max() > 0:
        magnitude = (magnitude / magnitude.max() * 255).astype(np.uint8)
    else:
        magnitude = magnitude.astype(np.uint8)

    return magnitude


def threshold_edges(edge_magnitude: np.ndarray) -> np.ndarray:
    """
    Threshold edge magnitude to binary edge map using Otsu's method.

    Parameters:
        edge_magnitude: Sobel edge magnitude image [0, 255]

    Returns:
        Binary edge map (True = edge pixel)
    """
    thresh = threshold_otsu(edge_magnitude)
    return edge_magnitude > thresh


def detect_edges(image: np.ndarray, ksize: int = DEFAULT_KSIZE) -> tuple[np.ndarray, np.ndarray]:
    """
    Full edge detection pipeline: Sobel + Otsu.

    Parameters:
        image: Input image (RGB or grayscale)
        ksize: Sobel kernel size (3 for 352px, 5 for 704px)

    Returns:
        Tuple of (binary edge map, edge magnitude for debugging)
    """
    magnitude = sobel_edges(image, ksize=ksize)
    edge_map = threshold_edges(magnitude)
    return edge_map, magnitude


# --- DP Skyline Search ---

def setup_boundaries(
    edge_map: np.ndarray,
    alpha: int | None = None,
    beta: int | None = None,
    tog: int = DEFAULT_TOG
) -> np.ndarray:
    """
    Set up boundary conditions for DP skyline search.

    Forces edges at left/right columns and top row near edges.
    This prevents the algorithm from selecting the image boundary as skyline.

    From paper §3:
    - Force all pixels in columns 0 and N-1 to be edges
    - Force top row pixels at j=0..α-1 and j=β..N-1 to be edges
    - Gap [α, β) must be > tog so top row can't be selected as skyline

    Parameters:
        edge_map: Binary edge map (M x N)
        alpha: End of left forced region in top row (default: tog)
        beta: Start of right forced region in top row (default: N - tog)
        tog: Gap tolerance

    Returns:
        Modified edge map with boundary conditions applied
    """
    edge_map = edge_map.copy()
    M, N = edge_map.shape

    # Default: force tog columns on each side of top row
    if alpha is None:
        alpha = tog
    if beta is None:
        beta = N - tog

    # Ensure gap is larger than tog (paper says β-α > tog)
    if beta - alpha <= tog:
        alpha = tog
        beta = N - tog

    # Force left and right columns to be edges
    edge_map[:, 0] = True
    edge_map[:, N - 1] = True

    # Force top row edges at left [0, alpha) and right [beta, N)
    # This creates an unbridgeable gap in the middle
    edge_map[0, :alpha] = True
    edge_map[0, beta:] = True

    return edge_map


def dp_skyline(
    edge_map: np.ndarray,
    delta: int = DEFAULT_DELTA,
    tog: int = DEFAULT_TOG,
    pun: float = DEFAULT_PUN
) -> np.ndarray:
    """
    Dynamic programming skyline search algorithm (Lie 2005, §3).

    Finds minimum-cost path from left to right through edge pixels.

    Parameters:
        edge_map: Binary edge map (M rows x N cols), with boundaries set up
        delta: Max vertical jump per column
        tog: Gap tolerance - how many columns ahead to search for edges
        pun: Penalty per dummy link when bridging gaps

    Returns:
        Skyline as array of row indices (length N), or -1 for invalid positions
    """
    M, N = edge_map.shape

    # Cost to reach each edge pixel
    cost = np.full((M, N), np.inf, dtype=np.float64)

    # Parent tracking: (prev_row, prev_col) for backtracking
    parent_row = np.full((M, N), -1, dtype=np.int32)
    parent_col = np.full((M, N), -1, dtype=np.int32)

    # --- Forward pass ---

    # Initialize first column: entry cost = (i+1)^2 for edge pixels
    for i in range(M):
        if edge_map[i, 0]:
            cost[i, 0] = (i + 1) ** 2

    # Process columns left to right
    for j in range(1, N):
        for i in range(M):
            if not edge_map[i, j]:
                continue

            best_cost = np.inf
            best_row = -1
            best_col = -1

            # Search backward for valid predecessors
            for d in range(1, min(tog, j) + 1):
                prev_j = j - d

                # Fan-shaped search region expands with distance
                # At distance d, search ±(delta + d - 1) rows
                search_range = delta + d - 1

                for prev_i in range(max(0, i - search_range), min(M, i + search_range + 1)):
                    if not edge_map[prev_i, prev_j]:
                        continue
                    if cost[prev_i, prev_j] == np.inf:
                        continue

                    # Link cost: |h-k| for direct neighbors, plus gap penalty
                    link_cost = abs(i - prev_i)
                    if d > 1:
                        # Add penalty for each dummy link (d-1 gaps)
                        link_cost += (d - 1) * pun

                    total = cost[prev_i, prev_j] + link_cost

                    if total < best_cost:
                        best_cost = total
                        best_row = prev_i
                        best_col = prev_j

                # If we found a valid predecessor at this distance, stop searching
                if best_row >= 0 and d == 1:
                    break

            if best_row >= 0:
                cost[i, j] = best_cost
                parent_row[i, j] = best_row
                parent_col[i, j] = best_col

    # Add exit cost at final column
    for i in range(M):
        if edge_map[i, N - 1] and cost[i, N - 1] < np.inf:
            cost[i, N - 1] += (i + 1) ** 2

    # --- Backward pass ---

    # Find minimum cost in final column
    final_costs = cost[:, N - 1]
    if np.all(final_costs == np.inf):
        # No valid path found
        return np.full(N, -1, dtype=np.int32)

    end_row = int(np.argmin(final_costs))

    # Backtrack to build skyline
    skyline = np.full(N, -1, dtype=np.int32)
    curr_row, curr_col = end_row, N - 1
    skyline[curr_col] = curr_row

    while curr_col > 0:
        prev_row = parent_row[curr_row, curr_col]
        prev_col = parent_col[curr_row, curr_col]

        if prev_row < 0:
            break

        # Interpolate dummy vertices for gaps
        if prev_col < curr_col - 1:
            # Linear interpolation between prev and curr
            for gap_col in range(prev_col + 1, curr_col):
                t = (gap_col - prev_col) / (curr_col - prev_col)
                interp_row = int(round(prev_row + t * (curr_row - prev_row)))
                skyline[gap_col] = interp_row

        skyline[prev_col] = prev_row
        curr_row, curr_col = prev_row, prev_col

    return skyline


def detect_skyline(
    image: np.ndarray,
    target_width: int = TARGET_WIDTH,
    delta: int = DEFAULT_DELTA,
    tog: int = DEFAULT_TOG,
    pun: float = DEFAULT_PUN,
    ksize: int = DEFAULT_KSIZE
) -> tuple[np.ndarray, float]:
    """
    High-level skyline detection API.

    Combines preprocessing and DP skyline search.

    Parameters:
        image: Input image (RGB or grayscale)
        target_width: Width to downscale to
        delta: Max vertical jump per column
        tog: Gap tolerance (columns)
        pun: Penalty per dummy link
        ksize: Sobel kernel size

    Returns:
        Tuple of (skyline row indices at target_width scale, scale factor)
    """
    # Downscale
    image_small, scale = downscale(image, target_width)

    # Edge detection
    edge_map, _ = detect_edges(image_small, ksize=ksize)

    # Set up boundaries
    edge_map = setup_boundaries(edge_map, tog=tog)

    # DP skyline search
    skyline = dp_skyline(edge_map, delta=delta, tog=tog, pun=pun)

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
        color: BGR color for skyline
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
        description="Lie 2005 Skyline Detection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("image", help="Input image path")
    parser.add_argument("-o", "--output", default="output/edges.jpg",
                        help="Output path for binary edge map")
    parser.add_argument("--target-width", type=int, default=TARGET_WIDTH,
                        help="Width to downscale to (352 = paper resolution)")
    parser.add_argument("--sobel-ksize", type=int, default=DEFAULT_KSIZE,
                        help="Sobel kernel size")
    parser.add_argument("--save-magnitude", help="Also save edge magnitude to this path")

    # DP skyline options
    parser.add_argument("--run-dp", action="store_true",
                        help="Run DP skyline detection and overlay on image")
    parser.add_argument("--delta", type=int, default=DEFAULT_DELTA,
                        help="Max vertical jump per column")
    parser.add_argument("--tog", type=int, default=DEFAULT_TOG,
                        help="Gap tolerance (columns)")
    parser.add_argument("--pun", type=float, default=DEFAULT_PUN,
                        help="Penalty per dummy link")
    parser.add_argument("--skyline-output", help="Output path for skyline overlay image")

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

    # Edge detection
    print(f"Detecting edges (Sobel ksize={args.sobel_ksize}, Otsu threshold)...")
    edge_map, edge_magnitude = detect_edges(image_small, ksize=args.sobel_ksize)
    edge_count = np.sum(edge_map)
    print(f"Edge pixels: {edge_count} ({100*edge_count/edge_map.size:.1f}%)")

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save binary edge map
    Image.fromarray((edge_map.astype(np.uint8) * 255)).save(str(output_path))
    print(f"Saved binary edge map to {output_path}")

    # Optionally save magnitude
    if args.save_magnitude:
        mag_path = Path(args.save_magnitude)
        mag_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(edge_magnitude).save(str(mag_path))
        print(f"Saved edge magnitude to {mag_path}")

    # Run DP skyline detection
    if args.run_dp:
        print(f"\nRunning DP skyline search (delta={args.delta}, tog={args.tog}, pun={args.pun})...")

        # Set up boundaries and run DP
        edge_map_bounded = setup_boundaries(edge_map, tog=args.tog)
        skyline = dp_skyline(edge_map_bounded, delta=args.delta, tog=args.tog, pun=args.pun)

        # Check coverage
        valid_count = np.sum(skyline >= 0)
        print(f"Skyline coverage: {valid_count}/{proc_width} columns ({100*valid_count/proc_width:.1f}%)")

        if valid_count > 0:
            min_row = np.min(skyline[skyline >= 0])
            max_row = np.max(skyline[skyline >= 0])
            print(f"Skyline row range: {min_row} - {max_row}")

            # Draw skyline on original image
            skyline_img = draw_skyline(image, skyline, scale, color=(255, 0, 0), thickness=4)

            # Determine output path
            if args.skyline_output:
                skyline_path = Path(args.skyline_output)
            else:
                skyline_path = output_path.with_stem(output_path.stem + "_skyline")

            skyline_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(skyline_img).save(str(skyline_path))
            print(f"Saved skyline overlay to {skyline_path}")

            # Save CSV for debugging
            csv_path = skyline_path.with_suffix(".csv")
            with open(csv_path, "w") as f:
                f.write("col,row,row_orig,is_edge\n")
                for col in range(len(skyline)):
                    row = skyline[col]
                    row_orig = int(row / scale) if row >= 0 else -1
                    is_edge = edge_map[row, col] if row >= 0 else False
                    f.write(f"{col},{row},{row_orig},{is_edge}\n")
            print(f"Saved skyline CSV to {csv_path}")
        else:
            print("WARNING: No valid skyline path found!")

    return 0


if __name__ == "__main__":
    exit(main())
