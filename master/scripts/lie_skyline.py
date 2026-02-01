#!/usr/bin/env python3
"""
Lie 2005 Skyline Detection Algorithm

Implements the dynamic programming skyline detection algorithm from:
Lie, W-N., Lin, T.C-I., Lin, T-C., & Hung, K-S. (2005).
"A robust dynamic programming algorithm to extract skyline in images for navigation."

Algorithm steps:
1. Edge Detection: Apply Sobel operator to luminance channel
2. Thresholding: Binary threshold using averaged Otsu + CP methods
3. Graph Construction: Convert edge map to multi-stage graph
4. DP Search: Find minimum-cost path from left to right edge
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.ImageOps import exif_transpose
from scipy import ndimage
from skimage.filters import threshold_otsu


def load_image_with_exif(path: str) -> np.ndarray:
    """Load image and auto-rotate based on EXIF orientation."""
    img = Image.open(path)
    img = exif_transpose(img)
    return np.array(img)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert RGB image to grayscale luminance."""
    if len(image.shape) == 2:
        return image.astype(np.float64)
    # Use standard luminance weights
    return (0.299 * image[:, :, 0] +
            0.587 * image[:, :, 1] +
            0.114 * image[:, :, 2]).astype(np.float64)


def sobel_edges(image: np.ndarray) -> np.ndarray:
    """
    Apply Sobel edge detection to grayscale image.

    Returns edge magnitude normalized to [0, 255].
    """
    # Sobel kernels
    sobel_x = ndimage.sobel(image, axis=1, mode='reflect')
    sobel_y = ndimage.sobel(image, axis=0, mode='reflect')

    # Magnitude
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

    # Normalize to [0, 255]
    if magnitude.max() > 0:
        magnitude = (magnitude / magnitude.max() * 255).astype(np.uint8)
    else:
        magnitude = magnitude.astype(np.uint8)

    return magnitude


def threshold_conditional_probability(edge_magnitude: np.ndarray) -> float:
    """
    Compute threshold using Conditional Probability (CP) method.

    Based on the observation that edge pixels typically have higher
    gradient magnitudes. Estimates threshold as the point where
    the conditional probability of being an edge changes significantly.
    """
    # Flatten and get histogram
    flat = edge_magnitude.flatten()
    hist, bin_edges = np.histogram(flat, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)

    # Avoid division by zero
    hist[hist == 0] = 1e-10

    # Cumulative sum from high to low (edge pixels tend to have high values)
    cum_high = np.cumsum(hist[::-1])[::-1]

    # Find threshold where the rate of change is maximum
    # This approximates where edge vs non-edge distributions separate
    diff = np.diff(cum_high)

    # Look for significant change point in upper half of histogram
    upper_half = diff[128:]
    if len(upper_half) > 0 and np.abs(upper_half).max() > 0:
        threshold_idx = 128 + np.argmax(np.abs(upper_half))
    else:
        # Fallback to median of non-zero pixels
        nonzero = flat[flat > 0]
        threshold_idx = int(np.median(nonzero)) if len(nonzero) > 0 else 128

    return float(threshold_idx)


def threshold_edges(edge_magnitude: np.ndarray, method: str = "averaged") -> np.ndarray:
    """
    Threshold edge magnitude to binary edge map.

    Parameters:
        edge_magnitude: Sobel edge magnitude image
        method: "otsu", "cp", or "averaged" (default)

    Returns:
        Binary edge map (True = edge pixel)
    """
    if method == "otsu":
        thresh = threshold_otsu(edge_magnitude)
    elif method == "cp":
        thresh = threshold_conditional_probability(edge_magnitude)
    else:  # averaged
        otsu_thresh = threshold_otsu(edge_magnitude)
        cp_thresh = threshold_conditional_probability(edge_magnitude)
        thresh = (otsu_thresh + cp_thresh) / 2

    return edge_magnitude > thresh


def build_graph_and_search(
    edge_map: np.ndarray,
    delta: int = 3,
    tog: int = 30,
    pun: float = 100.0
) -> np.ndarray:
    """
    DP search for minimum-cost skyline path.

    Uses full edge map and finds optimal path considering:
    - Vertex cost: (row+1)^2 at entry/exit (favors upper positions)
    - Link cost: |vertical_jump| for smoothness
    - Gap penalty: pun * gap_size when bridging

    Parameters:
        edge_map: Binary edge map (H x W)
        delta: Max vertical jump between adjacent columns
        tog: Max horizontal gap to bridge with dummy vertices
        pun: Penalty cost for each dummy link when bridging

    Returns:
        Array of y-coordinates (one per column), or -1 for columns with no path
    """
    height, width = edge_map.shape

    # Pre-compute edge row indices for each column for efficiency
    edge_rows = [np.where(edge_map[:, col])[0] for col in range(width)]

    # Ensure first and last columns have entry/exit points
    # If no edges, use the topmost edge from nearest column with edges
    if len(edge_rows[0]) == 0:
        for col in range(1, width):
            if len(edge_rows[col]) > 0:
                edge_rows[0] = edge_rows[col][:1]  # Use topmost
                break

    if len(edge_rows[-1]) == 0:
        for col in range(width - 2, -1, -1):
            if len(edge_rows[col]) > 0:
                edge_rows[-1] = edge_rows[col][:1]
                break

    # DP using sparse representation for efficiency
    # cost[col] = dict mapping row -> (min_cost, parent_col, parent_row)
    INF = float('inf')

    # Initialize first column with entry vertex costs
    cost = [{} for _ in range(width)]
    for row in edge_rows[0]:
        entry_cost = (row + 1) ** 2
        cost[0][row] = (entry_cost, -1, -1)

    # Forward pass
    for col in range(1, width):
        col_edges = edge_rows[col]
        if len(col_edges) == 0:
            continue

        # For efficiency, only consider edges within range of reachable positions
        # from previous columns
        for row in col_edges:
            best_cost = INF
            best_parent = (-1, -1)

            # Check direct connections from previous column
            if cost[col - 1]:
                for prev_row, (prev_cost, _, _) in cost[col - 1].items():
                    if abs(row - prev_row) <= delta:
                        link_cost = abs(row - prev_row)
                        total = prev_cost + link_cost
                        if total < best_cost:
                            best_cost = total
                            best_parent = (col - 1, prev_row)

            # Check gap bridging if no direct connection found
            if best_cost == INF:
                for gap in range(2, min(tog + 1, col + 1)):
                    prev_col = col - gap
                    if not cost[prev_col]:
                        continue

                    max_jump = delta * gap  # Allow proportional jump for gaps
                    for prev_row, (prev_cost, _, _) in cost[prev_col].items():
                        if abs(row - prev_row) <= max_jump:
                            link_cost = abs(row - prev_row)
                            gap_penalty = pun * (gap - 1)
                            total = prev_cost + link_cost + gap_penalty
                            if total < best_cost:
                                best_cost = total
                                best_parent = (prev_col, prev_row)

                    if best_cost < INF:
                        break  # Found connection, stop looking further back

            if best_cost < INF:
                cost[col][row] = (best_cost, best_parent[0], best_parent[1])

    # Find best endpoint in last column (adding exit vertex cost)
    best_end_cost = INF
    best_end_row = -1

    # Check last column
    for row, (row_cost, _, _) in cost[-1].items():
        exit_cost = (row + 1) ** 2
        total = row_cost + exit_cost
        if total < best_end_cost:
            best_end_cost = total
            best_end_row = row

    # If last column unreachable, find best reachable endpoint
    end_col = width - 1
    if best_end_row < 0:
        for col in range(width - 1, -1, -1):
            for row, (row_cost, _, _) in cost[col].items():
                exit_cost = (row + 1) ** 2
                total = row_cost + exit_cost
                if total < best_end_cost:
                    best_end_cost = total
                    best_end_row = row
                    end_col = col
            if best_end_row >= 0:
                break

    if best_end_row < 0:
        return np.full(width, -1, dtype=np.int32)

    # Backtrack to reconstruct path
    skyline = np.full(width, -1, dtype=np.int32)
    col, row = end_col, best_end_row

    while col >= 0:
        skyline[col] = row
        if col not in range(width) or row not in cost[col]:
            break
        _, prev_col, prev_row = cost[col][row]
        if prev_col < 0:
            break

        # Fill gaps with linear interpolation
        if prev_col < col - 1:
            for fill_col in range(prev_col + 1, col):
                t = (fill_col - prev_col) / (col - prev_col)
                skyline[fill_col] = int(prev_row + t * (row - prev_row))

        col, row = prev_col, prev_row

    # Fill remaining gaps at start
    first_valid_idx = -1
    for i in range(width):
        if skyline[i] >= 0:
            first_valid_idx = i
            break

    if first_valid_idx > 0:
        skyline[:first_valid_idx] = skyline[first_valid_idx]

    # Fill remaining gaps at end
    if end_col < width - 1:
        skyline[end_col + 1:] = skyline[end_col]

    return skyline


def detect_skyline_lie(
    image: np.ndarray,
    delta: int = 3,
    tog: int = 30,
    pun: float = 100.0,
    edge_method: str = "averaged"
) -> tuple[np.ndarray, np.ndarray]:
    """
    Main entry point for Lie 2005 skyline detection.

    Parameters:
        image: RGB or grayscale image
        delta: Max vertical jump between adjacent columns
        tog: Max horizontal gap to bridge
        pun: Gap penalty
        edge_method: Threshold method ("otsu", "cp", or "averaged")

    Returns:
        Tuple of (skyline y-coordinates, edge_map for debugging)
    """
    # Convert to grayscale
    gray = to_grayscale(image)

    # Edge detection
    edges = sobel_edges(gray)

    # Threshold
    edge_map = threshold_edges(edges, method=edge_method)

    # DP search
    skyline = build_graph_and_search(edge_map, delta, tog, pun)

    return skyline, edge_map


def draw_skyline(image: np.ndarray, skyline: np.ndarray, color: tuple = (255, 0, 0), thickness: int = 8) -> np.ndarray:
    """Draw skyline on image."""
    result = image.copy()
    height = image.shape[0]

    for x, y in enumerate(skyline):
        if 0 <= y < height:
            # Draw thick line
            for dy in range(-thickness // 2, thickness // 2 + 1):
                if 0 <= y + dy < height:
                    if len(result.shape) == 3:
                        result[y + dy, x] = color
                    else:
                        result[y + dy, x] = color[0]

    return result


def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(
        description="Lie 2005 Skyline Detection Algorithm",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("image", help="Input image path")
    parser.add_argument("-o", "--output", default="output/lie_skyline.jpg",
                        help="Output path")
    parser.add_argument("--delta", type=int, default=3,
                        help="Max vertical jump between adjacent columns")
    parser.add_argument("--tog", type=int, default=30,
                        help="Max horizontal gap to bridge")
    parser.add_argument("--pun", type=float, default=100.0,
                        help="Gap penalty cost")
    parser.add_argument("--edge-method", choices=["otsu", "cp", "averaged"],
                        default="averaged", help="Edge thresholding method")
    parser.add_argument("--overlay", action="store_true",
                        help="Draw skyline on original image (vs. edge map)")
    parser.add_argument("--thickness", type=int, default=5,
                        help="Line thickness in pixels")
    parser.add_argument("--debug", action="store_true",
                        help="Save intermediate edge map")

    args = parser.parse_args()

    # Load image
    print(f"Loading {args.image}...")
    image = load_image_with_exif(args.image)
    print(f"Image size: {image.shape[1]} x {image.shape[0]}")

    # Detect skyline
    print(f"Detecting skyline (delta={args.delta}, tog={args.tog}, pun={args.pun})...")
    skyline, edge_map = detect_skyline_lie(
        image,
        delta=args.delta,
        tog=args.tog,
        pun=args.pun,
        edge_method=args.edge_method
    )

    # Check for valid path
    valid_count = np.sum(skyline >= 0)
    print(f"Valid skyline points: {valid_count}/{len(skyline)}")

    if valid_count == 0:
        print("Error: No valid skyline path found")
        return 1

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Draw result
    if args.overlay:
        result = draw_skyline(image, skyline, thickness=args.thickness)
    else:
        # Draw on edge map (convert to RGB for colored line)
        edge_rgb = np.stack([edge_map.astype(np.uint8) * 255] * 3, axis=-1)
        result = draw_skyline(edge_rgb, skyline, color=(255, 0, 0), thickness=args.thickness)

    # Save result
    Image.fromarray(result).save(str(output_path))
    print(f"Saved result to {output_path}")

    # Save debug edge map
    if args.debug:
        debug_path = output_path.parent / f"{output_path.stem}_edges{output_path.suffix}"
        Image.fromarray((edge_map.astype(np.uint8) * 255)).save(str(debug_path))
        print(f"Saved edge map to {debug_path}")

    return 0


if __name__ == "__main__":
    exit(main())
