#!/usr/bin/env python3
"""
Skyline Comparison Visualization

Overlays 4 skylines on a geotagged image:
1. Lie 2005 image skyline (cyan)
2. Nagy 2020 image skyline (green)
3. DEM matched via Lie (red)
4. DEM matched via Nagy (magenta)
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from skyline.image.lie_05 import load_image, detect_skyline as detect_lie, draw_skyline
from skyline.image.nagy_20 import detect_skyline as detect_nagy
from skyline.dem.nagy_20 import determine_azimuth


def draw_dem_skyline(
    image: np.ndarray,
    debug: dict,
    color: tuple,
    thickness: int = 2,
    dotted: bool = False,
    dot_spacing: int = 10,
) -> tuple[int, int]:
    """
    Draw matched DEM skyline onto image.

    Projects DEM skyline (elevation angles) onto image pixels based on
    the matched azimuth and camera parameters.

    Parameters:
        image: RGB image to draw on (modified in place)
        debug: Debug dict from determine_azimuth()
        color: RGB color tuple
        thickness: Line thickness
        dotted: If True, draw as dotted/dashed line
        dot_spacing: Pixels between dots when dotted=True
    """
    h, w = image.shape[:2]
    fov_v = debug["fov_v"]
    fov_h = debug["camera_params"]["fov_h"]
    azimuth = debug.get("azimuth")

    # Get tilt-corrected DEM skyline if available, otherwise raw
    dem_skyline = debug.get("dem_skyline_corrected", debug["dem_skyline"])

    az_res = 0.1  # azimuth resolution in degrees

    # Extract DEM window at matched azimuth
    # The window spans [azimuth - fov_h/2, azimuth + fov_h/2]
    center_idx = int(azimuth / az_res) % len(dem_skyline)
    num_cols = int(fov_h / az_res)
    half = num_cols // 2

    indices = [(center_idx - half + i) % len(dem_skyline) for i in range(num_cols)]
    dem_window = dem_skyline[indices]
    # Flip horizontally - image left corresponds to HIGHER azimuth when camera faces away
    dem_window = dem_window[::-1]

    # Convert elevation angles to pixel rows
    # Image center = 0 degrees elevation (horizon)
    center_row = h / 2
    rows = center_row - (dem_window * h / fov_v)
    rows = np.clip(rows, 0, h - 1).astype(int)

    # Map to image columns - DEM window maps directly to image width
    cols = np.linspace(0, w - 1, len(rows)).astype(int)

    # Find highest point (minimum row)
    min_row_idx = np.argmin(rows)
    highest_x = cols[min_row_idx]
    highest_y = rows[min_row_idx]

    # Draw line segments (dotted or solid)
    if dotted:
        # Draw dots at regular intervals
        for i in range(0, len(cols), dot_spacing):
            cv2.circle(image, (cols[i], rows[i]), thickness, color, -1)
    else:
        for i in range(len(cols) - 1):
            cv2.line(image, (cols[i], rows[i]), (cols[i + 1], rows[i + 1]), color, thickness)

    return int(highest_x), int(highest_y)


def main():
    parser = argparse.ArgumentParser(
        description="Skyline comparison: 4 methods overlaid on image"
    )
    parser.add_argument("image", help="Path to geotagged image")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--dem-dir", default="dem", help="DEM tiles directory")
    parser.add_argument(
        "--dem-resolution",
        choices=["50cm", "200cm"],
        default="200cm",
        help="DEM resolution",
    )
    parser.add_argument(
        "--search-window",
        type=float,
        default=45.0,
        help="Search window +/- degrees around compass heading",
    )
    args = parser.parse_args()

    print(f"Loading image: {args.image}")
    image = load_image(args.image)
    output = image.copy()
    h, w = image.shape[:2]
    print(f"  Size: {w} x {h}")

    # Line thickness settings
    img_thickness = 4  # Image skylines (solid)
    dem_thickness = 6  # DEM skylines (dotted)

    # 1. Lie 2005 image skyline (cyan)
    print("\n[1/4] Detecting Lie 2005 image skyline...")
    skyline_lie, scale_lie = detect_lie(image)
    valid_lie = np.sum(skyline_lie >= 0)
    print(f"  Valid columns: {valid_lie}/{len(skyline_lie)}")
    # Find highest point (minimum row value)
    valid_mask = skyline_lie >= 0
    if valid_mask.any():
        min_row_idx = np.argmin(np.where(valid_mask, skyline_lie, 99999))
        min_row = skyline_lie[min_row_idx]
        x_pixel_lie = int(min_row_idx / scale_lie)
        y_pixel_lie = int(min_row / scale_lie)
        print(f"  Highest point: x={x_pixel_lie}, y={y_pixel_lie} (col {min_row_idx} at scale)")
    output = draw_skyline(output, skyline_lie, scale_lie, color=(0, 255, 255), thickness=img_thickness)

    # 2. Nagy 2020 image skyline (green)
    print("\n[2/4] Detecting Nagy 2020 image skyline...")
    skyline_nagy, scale_nagy = detect_nagy(image)
    valid_nagy = np.sum(skyline_nagy >= 0)
    print(f"  Valid columns: {valid_nagy}/{len(skyline_nagy)}")
    # Find highest point
    valid_mask = skyline_nagy >= 0
    if valid_mask.any():
        min_row_idx = np.argmin(np.where(valid_mask, skyline_nagy, 99999))
        min_row = skyline_nagy[min_row_idx]
        x_pixel_nagy_img = int(min_row_idx / scale_nagy)
        y_pixel_nagy_img = int(min_row / scale_nagy)
        print(f"  Highest point: x={x_pixel_nagy_img}, y={y_pixel_nagy_img} (col {min_row_idx} at scale)")
    output = draw_skyline(output, skyline_nagy, scale_nagy, color=(0, 255, 0), thickness=img_thickness)

    # 3. DEM match via Lie (red, dotted)
    print("\n[3/4] Matching DEM skyline via Lie method...")
    az_lie, corr_lie, debug_lie = determine_azimuth(
        args.image,
        dem_dir=args.dem_dir,
        dem_resolution=args.dem_resolution,
        search_window=args.search_window,
        skyline_method="lie",
        verbose=True,
    )
    # Use matched azimuth for drawing
    debug_lie["azimuth"] = az_lie
    dem_x_lie, dem_y_lie = draw_dem_skyline(output, debug_lie, color=(255, 0, 0), thickness=dem_thickness, dotted=True)
    print(f"  DEM highest point: x={dem_x_lie}, y={dem_y_lie}")

    # 4. DEM match via Nagy (magenta, dotted)
    print("\n[4/4] Matching DEM skyline via Nagy method...")
    az_nagy, corr_nagy, debug_nagy = determine_azimuth(
        args.image,
        dem_dir=args.dem_dir,
        dem_resolution=args.dem_resolution,
        search_window=args.search_window,
        skyline_method="nagy",
        verbose=True,
    )
    # Use matched azimuth for drawing
    debug_nagy["azimuth"] = az_nagy
    dem_x_nagy, dem_y_nagy = draw_dem_skyline(output, debug_nagy, color=(255, 0, 255), thickness=dem_thickness, dotted=True)
    print(f"  DEM highest point: x={dem_x_nagy}, y={dem_y_nagy}")

    # Save output
    Path(args.output_dir).mkdir(exist_ok=True)
    out_path = Path(args.output_dir) / f"{Path(args.image).stem}_skylines.jpg"
    Image.fromarray(output).save(out_path, quality=95)

    # Print summary
    compass = debug_lie["camera_params"].get("compass_heading")
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Compass heading: {compass:.1f}" if compass else "Compass heading: N/A")
    print()
    print("Skyline Colors:")
    print("  Cyan:    Lie 2005 image skyline")
    print("  Green:   Nagy 2020 image skyline")
    print("  Red:     DEM matched via Lie")
    print("  Magenta: DEM matched via Nagy")
    print()
    print("DEM Match Results:")
    print(f"  Lie method:  azimuth={az_lie:.1f}, correlation={corr_lie:.3f}")
    print(f"  Nagy method: azimuth={az_nagy:.1f}, correlation={corr_nagy:.3f}")
    if compass:
        diff_lie = az_lie - compass
        diff_nagy = az_nagy - compass
        if diff_lie > 180:
            diff_lie -= 360
        elif diff_lie < -180:
            diff_lie += 360
        if diff_nagy > 180:
            diff_nagy -= 360
        elif diff_nagy < -180:
            diff_nagy += 360
        print(f"  Lie diff from compass:  {diff_lie:+.1f}")
        print(f"  Nagy diff from compass: {diff_nagy:+.1f}")
    print()
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
