#!/usr/bin/env python3
"""
Skyline Comparison Visualization

Overlays 4 skylines on a geotagged image:
1. Lie 2005 image skyline (cyan)
2. Nagy 2020 image skyline (green)
3. DEM matched via Lie (red)
4. DEM matched via Nagy (magenta)

Outputs:
- {stem}_skylines.jpg: Image with overlaid skylines
- {stem}_skylines.csv: Pixel coordinates for all 4 skylines
- {stem}_stats.json: Key statistics and parameters
- {stem}_plot.png: Matplotlib visualization with correlation curves
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from skyline.image.lie_05 import load_image, detect_skyline as detect_lie, draw_skyline
from skyline.image.nagy_20 import detect_skyline as detect_nagy
from skyline.dem.nagy_20 import determine_azimuth


def get_dem_skyline_coords(
    debug: dict,
    image_width: int,
    image_height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Get DEM skyline pixel coordinates for an image.

    Returns:
        Tuple of (x_coords, y_coords) arrays in image pixels
    """
    h, w = image_height, image_width
    fov_v = debug["fov_v"]
    fov_h = debug["camera_params"]["fov_h"]
    azimuth = debug.get("azimuth")

    # Get tilt-corrected DEM skyline if available, otherwise raw
    dem_skyline = debug.get("dem_skyline_corrected", debug["dem_skyline"])

    az_res = 0.1  # azimuth resolution in degrees

    # Extract DEM window at matched azimuth
    center_idx = int(azimuth / az_res) % len(dem_skyline)
    num_cols = int(fov_h / az_res)
    half = num_cols // 2

    indices = [(center_idx - half + i) % len(dem_skyline) for i in range(num_cols)]
    dem_window = dem_skyline[indices]
    # Flip horizontally - image left corresponds to HIGHER azimuth when camera faces away
    dem_window = dem_window[::-1]

    # Convert elevation angles to pixel rows
    # Apply pitch offset if orientation was optimized
    pitch_offset = debug.get("pitch_optimized", 0.0) - debug.get("pitch_init", 0.0)
    center_row = h / 2
    rows = center_row - ((dem_window + pitch_offset) * h / fov_v)
    rows = np.clip(rows, 0, h - 1).astype(int)

    # Map to image columns
    cols = np.linspace(0, w - 1, len(rows)).astype(int)

    return cols, rows


def draw_dem_skyline(
    image: np.ndarray,
    debug: dict,
    color: tuple,
    thickness: int = 2,
    dotted: bool = False,
    dot_spacing: int = 10,
) -> tuple[int, int, np.ndarray, np.ndarray]:
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

    Returns:
        Tuple of (highest_x, highest_y, x_coords, y_coords)
    """
    h, w = image.shape[:2]
    cols, rows = get_dem_skyline_coords(debug, w, h)

    # Find highest point (minimum row)
    min_row_idx = np.argmin(rows)
    highest_x = cols[min_row_idx]
    highest_y = rows[min_row_idx]

    # Draw line segments (dashed or solid)
    if dotted:
        # Draw dashed line: alternating segments
        dash_len = dot_spacing
        gap_len = dot_spacing // 2
        i = 0
        while i < len(cols) - 1:
            # Draw dash segment
            end = min(i + dash_len, len(cols) - 1)
            for j in range(i, end):
                cv2.line(image, (cols[j], rows[j]), (cols[j + 1], rows[j + 1]), color, thickness)
            # Skip gap
            i = end + gap_len
    else:
        for i in range(len(cols) - 1):
            cv2.line(image, (cols[i], rows[i]), (cols[i + 1], rows[i + 1]), color, thickness)

    return int(highest_x), int(highest_y), cols, rows


def get_image_skyline_coords(
    skyline: np.ndarray,
    scale: float,
    image_width: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert scaled skyline to full-resolution pixel coordinates.

    Returns:
        Tuple of (x_coords, y_coords) arrays. Invalid points have y=-1.
    """
    num_cols = len(skyline)
    # Map scaled columns to full image width
    x_coords = np.linspace(0, image_width - 1, num_cols).astype(int)
    # Scale row values back to full resolution
    y_coords = np.where(skyline >= 0, (skyline / scale).astype(int), -1)
    return x_coords, y_coords


def save_skylines_csv(
    path: Path,
    image_width: int,
    lie_img: tuple[np.ndarray, np.ndarray],
    nagy_img: tuple[np.ndarray, np.ndarray],
    lie_dem: tuple[np.ndarray, np.ndarray],
    nagy_dem: tuple[np.ndarray, np.ndarray],
) -> None:
    """
    Save all skyline coordinates to CSV.

    Columns: x, lie_img_y, nagy_img_y, lie_dem_y, nagy_dem_y
    """
    # Resample all to common x coordinates (image width)
    x_common = np.arange(image_width)

    def resample(x, y, x_new):
        """Resample y values to new x coordinates."""
        valid = y >= 0
        if not valid.any():
            return np.full(len(x_new), -1)
        return np.interp(x_new, x[valid], y[valid], left=-1, right=-1).astype(int)

    lie_img_y = resample(lie_img[0], lie_img[1], x_common)
    nagy_img_y = resample(nagy_img[0], nagy_img[1], x_common)
    lie_dem_y = resample(lie_dem[0], lie_dem[1], x_common)
    nagy_dem_y = resample(nagy_dem[0], nagy_dem[1], x_common)

    with open(path, "w") as f:
        f.write("x,lie_img_y,nagy_img_y,lie_dem_y,nagy_dem_y\n")
        for i in range(image_width):
            f.write(f"{i},{lie_img_y[i]},{nagy_img_y[i]},{lie_dem_y[i]},{nagy_dem_y[i]}\n")


def save_stats_json(
    path: Path,
    image_path: str,
    image_size: tuple[int, int],
    camera_params: dict,
    lie_img_stats: dict,
    nagy_img_stats: dict,
    lie_dem_stats: dict,
    nagy_dem_stats: dict,
) -> None:
    """Save statistics and parameters to JSON."""
    stats = {
        "timestamp": datetime.now().isoformat(),
        "input_image": str(image_path),
        "image_size": {"width": image_size[0], "height": image_size[1]},
        "camera_params": {
            "fov_h": camera_params.get("fov_h"),
            "compass_heading": camera_params.get("compass_heading"),
            "pitch": camera_params.get("pitch"),
            "roll": camera_params.get("roll"),
        },
        "skylines": {
            "lie_image": lie_img_stats,
            "nagy_image": nagy_img_stats,
            "lie_dem": lie_dem_stats,
            "nagy_dem": nagy_dem_stats,
        },
    }
    with open(path, "w") as f:
        json.dump(stats, f, indent=2)


def create_matplotlib_figure(
    image: np.ndarray,
    lie_img_coords: tuple[np.ndarray, np.ndarray],
    nagy_img_coords: tuple[np.ndarray, np.ndarray],
    lie_dem_coords: tuple[np.ndarray, np.ndarray],
    nagy_dem_coords: tuple[np.ndarray, np.ndarray],
    debug_lie: dict,
    debug_nagy: dict,
    compass: float | None,
) -> plt.Figure:
    """
    Create matplotlib figure with image overlay and correlation curves.

    Returns:
        matplotlib Figure object
    """
    fig = plt.figure(figsize=(16, 12))

    # Layout: 2x2 grid
    # Top row: image with skylines (spans both columns)
    # Bottom row: correlation curves for Lie and Nagy

    # Top: Image with skylines
    ax_img = fig.add_subplot(2, 1, 1)
    ax_img.imshow(image)

    # Plot skylines on image
    valid = lie_img_coords[1] >= 0
    ax_img.plot(lie_img_coords[0][valid], lie_img_coords[1][valid],
                'c-', linewidth=1.5, label='Lie image', alpha=0.8)

    valid = nagy_img_coords[1] >= 0
    ax_img.plot(nagy_img_coords[0][valid], nagy_img_coords[1][valid],
                'g-', linewidth=1.5, label='Nagy image', alpha=0.8)

    ax_img.plot(lie_dem_coords[0], lie_dem_coords[1],
                'r--', linewidth=1.5, label='DEM (Lie)', alpha=0.8)

    ax_img.plot(nagy_dem_coords[0], nagy_dem_coords[1],
                'm--', linewidth=1.5, label='DEM (Nagy)', alpha=0.8)

    ax_img.set_xlim(0, image.shape[1])
    ax_img.set_ylim(image.shape[0], 0)  # Invert y-axis
    ax_img.set_title('Skyline Comparison')
    ax_img.legend(loc='upper right')
    ax_img.axis('off')

    # Bottom left: Lie correlation curve
    ax_corr_lie = fig.add_subplot(2, 2, 3)
    if "correlation_curve" in debug_lie:
        azimuths = debug_lie.get("search_azimuths", np.arange(len(debug_lie["correlation_curve"])) * 0.1)
        ax_corr_lie.plot(azimuths, debug_lie["correlation_curve"], 'r-', linewidth=1)
        ax_corr_lie.axvline(debug_lie["azimuth"], color='r', linestyle='--',
                           label=f'Match: {debug_lie["azimuth"]:.1f}°')
        if compass is not None:
            ax_corr_lie.axvline(compass, color='g', linestyle=':',
                               label=f'Compass: {compass:.1f}°')
        ax_corr_lie.set_xlabel('Azimuth (°)')
        ax_corr_lie.set_ylabel('Correlation')
        ax_corr_lie.set_title(f'Lie Method (corr={debug_lie.get("correlation", 0):.3f})')
        ax_corr_lie.legend()
        ax_corr_lie.grid(True, alpha=0.3)

    # Bottom right: Nagy correlation curve
    ax_corr_nagy = fig.add_subplot(2, 2, 4)
    if "correlation_curve" in debug_nagy:
        azimuths = debug_nagy.get("search_azimuths", np.arange(len(debug_nagy["correlation_curve"])) * 0.1)
        ax_corr_nagy.plot(azimuths, debug_nagy["correlation_curve"], 'm-', linewidth=1)
        ax_corr_nagy.axvline(debug_nagy["azimuth"], color='m', linestyle='--',
                            label=f'Match: {debug_nagy["azimuth"]:.1f}°')
        if compass is not None:
            ax_corr_nagy.axvline(compass, color='g', linestyle=':',
                                label=f'Compass: {compass:.1f}°')
        ax_corr_nagy.set_xlabel('Azimuth (°)')
        ax_corr_nagy.set_ylabel('Correlation')
        ax_corr_nagy.set_title(f'Nagy Method (corr={debug_nagy.get("correlation", 0):.3f})')
        ax_corr_nagy.legend()
        ax_corr_nagy.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


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
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip matplotlib plot generation",
    )
    parser.add_argument(
        "--optimize-orientation",
        action="store_true",
        help="Optimize roll (Brent's method) and pitch (closed-form) after azimuth matching",
    )
    parser.add_argument(
        "--roll-range",
        type=float,
        default=5.0,
        help="Search ± this many degrees for roll optimization (default: 5.0)",
    )
    args = parser.parse_args()

    print(f"Loading image: {args.image}")
    image = load_image(args.image)
    output = image.copy()
    h, w = image.shape[:2]
    print(f"  Size: {w} x {h}")

    # Line thickness settings
    img_thickness = 6   # Image skylines (solid)
    dem_thickness = 8   # DEM skylines (dashed)

    # 1. Lie 2005 image skyline (cyan)
    print("\n[1/4] Detecting Lie 2005 image skyline...")
    skyline_lie, scale_lie = detect_lie(image)
    valid_lie = int(np.sum(skyline_lie >= 0))
    print(f"  Valid columns: {valid_lie}/{len(skyline_lie)}")
    lie_img_coords = get_image_skyline_coords(skyline_lie, scale_lie, w)
    # Find highest point (minimum row value)
    valid_mask = skyline_lie >= 0
    x_pixel_lie, y_pixel_lie = -1, -1
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
    valid_nagy = int(np.sum(skyline_nagy >= 0))
    print(f"  Valid columns: {valid_nagy}/{len(skyline_nagy)}")
    nagy_img_coords = get_image_skyline_coords(skyline_nagy, scale_nagy, w)
    # Find highest point
    valid_mask = skyline_nagy >= 0
    x_pixel_nagy_img, y_pixel_nagy_img = -1, -1
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
        optimize_orientation=args.optimize_orientation,
        roll_range=args.roll_range,
    )
    # Use matched azimuth for drawing
    debug_lie["azimuth"] = az_lie
    debug_lie["correlation"] = corr_lie
    dem_x_lie, dem_y_lie, lie_dem_x, lie_dem_y = draw_dem_skyline(
        output, debug_lie, color=(255, 0, 0), thickness=dem_thickness, dotted=True
    )
    lie_dem_coords = (lie_dem_x, lie_dem_y)
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
        optimize_orientation=args.optimize_orientation,
        roll_range=args.roll_range,
    )
    # Use matched azimuth for drawing
    debug_nagy["azimuth"] = az_nagy
    debug_nagy["correlation"] = corr_nagy
    dem_x_nagy, dem_y_nagy, nagy_dem_x, nagy_dem_y = draw_dem_skyline(
        output, debug_nagy, color=(255, 0, 255), thickness=dem_thickness, dotted=True
    )
    nagy_dem_coords = (nagy_dem_x, nagy_dem_y)
    print(f"  DEM highest point: x={dem_x_nagy}, y={dem_y_nagy}")

    # Get compass heading for stats
    compass = debug_lie["camera_params"].get("compass_heading")

    # Calculate compass differences
    diff_lie, diff_nagy = None, None
    if compass is not None:
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

    # Save outputs
    Path(args.output_dir).mkdir(exist_ok=True)
    stem = Path(args.image).stem

    # 1. Save image with overlaid skylines
    out_img_path = Path(args.output_dir) / f"{stem}_skylines.jpg"
    Image.fromarray(output).save(out_img_path, quality=95)
    print(f"\nSaved: {out_img_path}")

    # 2. Save CSV with skyline coordinates
    out_csv_path = Path(args.output_dir) / f"{stem}_skylines.csv"
    save_skylines_csv(
        out_csv_path,
        w,
        lie_img_coords,
        nagy_img_coords,
        lie_dem_coords,
        nagy_dem_coords,
    )
    print(f"Saved: {out_csv_path}")

    # 3. Save JSON with statistics
    out_json_path = Path(args.output_dir) / f"{stem}_stats.json"
    # Build stats dicts, including optimization results if available
    lie_dem_stats = {
        "azimuth": az_lie,
        "correlation": corr_lie,
        "compass_diff": diff_lie,
        "highest_point": {"x": dem_x_lie, "y": dem_y_lie},
    }
    nagy_dem_stats = {
        "azimuth": az_nagy,
        "correlation": corr_nagy,
        "compass_diff": diff_nagy,
        "highest_point": {"x": dem_x_nagy, "y": dem_y_nagy},
    }

    # Add optimization results if present
    if "roll_optimized" in debug_lie:
        lie_dem_stats["orientation_optimization"] = {
            "roll_init": debug_lie["roll_init"],
            "roll_optimized": debug_lie["roll_optimized"],
            "pitch_init": debug_lie["pitch_init"],
            "pitch_optimized": debug_lie["pitch_optimized"],
            "pitch_offset": debug_lie["pitch_offset"],
            "correlation_before_roll": debug_lie["correlation_before_roll"],
            "correlation_after_roll": debug_lie["correlation_after_roll"],
        }
    if "roll_optimized" in debug_nagy:
        nagy_dem_stats["orientation_optimization"] = {
            "roll_init": debug_nagy["roll_init"],
            "roll_optimized": debug_nagy["roll_optimized"],
            "pitch_init": debug_nagy["pitch_init"],
            "pitch_optimized": debug_nagy["pitch_optimized"],
            "pitch_offset": debug_nagy["pitch_offset"],
            "correlation_before_roll": debug_nagy["correlation_before_roll"],
            "correlation_after_roll": debug_nagy["correlation_after_roll"],
        }

    save_stats_json(
        out_json_path,
        args.image,
        (w, h),
        debug_lie["camera_params"],
        {
            "valid_columns": valid_lie,
            "total_columns": len(skyline_lie),
            "highest_point": {"x": x_pixel_lie, "y": y_pixel_lie},
            "scale": scale_lie,
        },
        {
            "valid_columns": valid_nagy,
            "total_columns": len(skyline_nagy),
            "highest_point": {"x": x_pixel_nagy_img, "y": y_pixel_nagy_img},
            "scale": scale_nagy,
        },
        lie_dem_stats,
        nagy_dem_stats,
    )
    print(f"Saved: {out_json_path}")

    # 4. Save matplotlib figure
    if not args.no_plot:
        out_plot_path = Path(args.output_dir) / f"{stem}_plot.png"
        fig = create_matplotlib_figure(
            image,
            lie_img_coords,
            nagy_img_coords,
            lie_dem_coords,
            nagy_dem_coords,
            debug_lie,
            debug_nagy,
            compass,
        )
        fig.savefig(out_plot_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out_plot_path}")

    # Print summary
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
    print(f"  Lie method:  azimuth={az_lie:.1f}°, correlation={corr_lie:.3f}")
    print(f"  Nagy method: azimuth={az_nagy:.1f}°, correlation={corr_nagy:.3f}")
    if diff_lie is not None:
        print(f"  Lie diff from compass:  {diff_lie:+.1f}°")
        print(f"  Nagy diff from compass: {diff_nagy:+.1f}°")

    # Print orientation optimization results if available
    if "roll_optimized" in debug_lie or "roll_optimized" in debug_nagy:
        print()
        print("Orientation Optimization:")
        if "roll_optimized" in debug_lie:
            print(f"  Lie: roll {debug_lie['roll_init']:.2f}° → {debug_lie['roll_optimized']:.2f}°, "
                  f"pitch {debug_lie['pitch_init']:.2f}° → {debug_lie['pitch_optimized']:.2f}°")
        if "roll_optimized" in debug_nagy:
            print(f"  Nagy: roll {debug_nagy['roll_init']:.2f}° → {debug_nagy['roll_optimized']:.2f}°, "
                  f"pitch {debug_nagy['pitch_init']:.2f}° → {debug_nagy['pitch_optimized']:.2f}°")


if __name__ == "__main__":
    main()
