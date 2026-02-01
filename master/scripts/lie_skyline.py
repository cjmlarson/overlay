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

    Optimized implementation using topmost edges per column.
    Cost function:
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

    # Find topmost edge in each column - these are our skyline candidates
    # This is much more efficient than tracking all edges
    topmost = np.full(width, -1, dtype=np.int32)
    for col in range(width):
        edges = np.where(edge_map[:, col])[0]
        if len(edges) > 0:
            topmost[col] = edges[0]

    # Find valid column ranges
    valid_cols = np.where(topmost >= 0)[0]
    if len(valid_cols) == 0:
        return np.full(width, -1, dtype=np.int32)

    first_valid = valid_cols[0]
    last_valid = valid_cols[-1]

    # DP arrays
    INF = float('inf')
    cost = np.full(width, INF, dtype=np.float64)
    parent = np.full(width, -1, dtype=np.int32)

    # Initialize first valid column with entry vertex cost
    cost[first_valid] = (topmost[first_valid] + 1) ** 2

    # Forward pass - only process valid columns
    for i in range(1, len(valid_cols)):
        col = valid_cols[i]
        row = topmost[col]

        best_cost = INF
        best_parent = -1

        # Look back at previous valid columns within tog range
        for j in range(i - 1, -1, -1):
            prev_col = valid_cols[j]
            gap = col - prev_col

            if gap > tog:
                break  # Too far back

            if cost[prev_col] == INF:
                continue

            prev_row = topmost[prev_col]
            max_jump = delta * gap  # Allow proportional jump for gaps

            if abs(row - prev_row) <= max_jump:
                link_cost = abs(row - prev_row)
                gap_penalty = pun * (gap - 1) if gap > 1 else 0
                total = cost[prev_col] + link_cost + gap_penalty

                if total < best_cost:
                    best_cost = total
                    best_parent = prev_col

        if best_cost < INF:
            cost[col] = best_cost
            parent[col] = best_parent

    # Add exit vertex cost to reachable columns and find best endpoint
    best_end_cost = INF
    best_end_col = -1

    for col in valid_cols:
        if cost[col] < INF:
            exit_cost = (topmost[col] + 1) ** 2
            total = cost[col] + exit_cost
            if total < best_end_cost:
                best_end_cost = total
                best_end_col = col

    if best_end_col < 0:
        return np.full(width, -1, dtype=np.int32)

    # Backtrack to reconstruct path
    skyline = np.full(width, -1, dtype=np.int32)
    col = best_end_col

    while col >= 0:
        skyline[col] = topmost[col]
        prev_col = parent[col]

        if prev_col >= 0 and prev_col < col - 1:
            # Fill gaps with linear interpolation
            prev_row = topmost[prev_col]
            curr_row = topmost[col]
            for fill_col in range(prev_col + 1, col):
                t = (fill_col - prev_col) / (col - prev_col)
                skyline[fill_col] = int(prev_row + t * (curr_row - prev_row))

        col = prev_col

    # Fill remaining gaps at start and end
    first_filled = np.argmax(skyline >= 0)
    if first_filled > 0:
        skyline[:first_filled] = skyline[first_filled]

    last_filled = width - 1 - np.argmax(skyline[::-1] >= 0)
    if last_filled < width - 1:
        skyline[last_filled + 1:] = skyline[last_filled]

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
