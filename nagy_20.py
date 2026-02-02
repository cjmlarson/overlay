#!/usr/bin/env python3
"""
Panoramic Skyline Generation from DEM

Implements the DEM-based skyline extraction algorithm from:
Nagy, G. (2020) "Determining the Orientation of Photos Containing Mountain Peaks"
Section 3.1: Computing the skyline from the DEM

This module generates a 360° panoramic skyline from DEM data given a camera position.
"""

import numpy as np
import rasterio


def save_skyline_csv(
    path: str,
    skyline: np.ndarray,
    distances: np.ndarray | None = None,
    azimuth_resolution: float = 0.1,
) -> None:
    """
    Save skyline to CSV file.

    Args:
        path: Output CSV file path
        skyline: Array of elevation angles (degrees)
        distances: Optional array of distances (meters)
        azimuth_resolution: Angular resolution used to generate skyline
    """
    num_bins = len(skyline)
    azimuths = np.arange(num_bins) * azimuth_resolution

    with open(path, 'w') as f:
        if distances is not None:
            f.write("azimuth_deg,elevation_deg,distance_m\n")
            for i in range(num_bins):
                f.write(f"{azimuths[i]:.1f},{skyline[i]:.4f},{distances[i]:.1f}\n")
        else:
            f.write("azimuth_deg,elevation_deg\n")
            for i in range(num_bins):
                f.write(f"{azimuths[i]:.1f},{skyline[i]:.4f}\n")


def get_camera_elevation(
    grid: np.ndarray,
    transform: rasterio.Affine,
    cam_e: float,
    cam_n: float,
    height_above_ground: float = 2.0,
) -> float:
    """
    Get camera elevation from DEM plus height buffer.

    Args:
        grid: 2D elevation array from load_dem_tiles
        transform: Affine transform for coordinate conversion
        cam_e: Camera easting (Swiss coords, meters)
        cam_n: Camera northing (Swiss coords, meters)
        height_above_ground: Height of camera above ground (default 2m)

    Returns:
        Camera elevation in meters (ground elevation + height buffer)

    Raises:
        ValueError: If camera position is outside DEM coverage
    """
    from utils import sample_elevation

    ground_z = sample_elevation(grid, transform, cam_e, cam_n)
    if np.isnan(ground_z):
        raise ValueError(f"Camera position ({cam_e}, {cam_n}) is outside DEM coverage")

    return ground_z + height_above_ground


def compute_panoramic_skyline(
    grid: np.ndarray,
    transform: rasterio.Affine,
    cam_e: float,
    cam_n: float,
    cam_z: float,
    azimuth_resolution: float = 0.1,
    max_distance: float = 10000,
    min_distance: float = 100,
    return_distances: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """
    Compute 360° panoramic skyline from DEM.

    Uses the DEM iteration approach from Nagy 2020 §3.1:
    For each DEM point, compute its azimuth and elevation angle from the camera,
    then update the maximum elevation angle for that azimuth bin.

    Args:
        grid: 2D elevation array from load_dem_tiles
        transform: Affine transform for coordinate conversion
        cam_e: Camera easting (Swiss coords, meters)
        cam_n: Camera northing (Swiss coords, meters)
        cam_z: Camera elevation (meters)
        azimuth_resolution: Angular resolution in degrees (default 0.1° → 3600 samples)
        max_distance: Maximum horizontal distance to consider (meters)
        min_distance: Minimum horizontal distance to consider (meters)
        return_distances: If True, also return distance to each skyline point

    Returns:
        If return_distances=False:
            1D numpy array of elevation angles (degrees), indexed by azimuth.
        If return_distances=True:
            Tuple of (skyline, distances):
            - skyline: elevation angles in degrees
            - distances: horizontal distance in meters to skyline-defining point

        Azimuth indexing:
        - skyline[0] = elevation angle looking North (0°)
        - skyline[900] = elevation angle looking East (90°)
        - skyline[1800] = elevation angle looking South (180°)
        - skyline[2700] = elevation angle looking West (270°)
    """
    h, w = grid.shape
    num_bins = int(360 / azimuth_resolution)

    # Initialize skyline to -90° (below horizon)
    skyline = np.full(num_bins, -90.0, dtype=np.float64)

    # Generate world coordinates for all grid points
    # Transform maps pixel (col, row) to world (easting, northing)
    rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')

    # Apply affine transform: (E, N) = transform * (col, row)
    # Affine: E = a*col + b*row + c, N = d*col + e*row + f
    eastings = transform.a * cols + transform.b * rows + transform.c
    northings = transform.d * cols + transform.e * rows + transform.f

    # Get elevations
    elevations = grid

    # Compute relative positions from camera
    de = eastings - cam_e  # delta easting
    dn = northings - cam_n  # delta northing
    dz = elevations - cam_z  # delta elevation

    # Compute horizontal distance
    rho = np.sqrt(de**2 + dn**2)

    # Create distance mask
    valid = (rho >= min_distance) & (rho <= max_distance) & ~np.isnan(elevations)

    # Compute azimuth: atan2(dE, dN) gives angle from North
    # Note: atan2(y, x) with y=dE, x=dN gives 0° at North, 90° at East
    phi = np.degrees(np.arctan2(de, dn))  # Range: -180 to 180
    phi = np.mod(phi, 360)  # Convert to 0-360 range

    # Compute elevation angle
    theta = np.degrees(np.arctan2(dz, rho))

    # Apply mask
    phi_valid = phi[valid]
    theta_valid = theta[valid]
    rho_valid = rho[valid]

    # Bin azimuths
    bins = np.floor(phi_valid / azimuth_resolution).astype(np.int32)
    bins = np.clip(bins, 0, num_bins - 1)  # Safety clamp

    # Fast path: use np.maximum.at for efficient scatter-reduce O(n)
    np.maximum.at(skyline, bins, theta_valid)

    # Clip negative values to 0 (horizon extends beyond DEM coverage)
    skyline = np.maximum(skyline, 0)

    if not return_distances:
        return skyline.astype(np.float32)

    # Distance path: two-pass vectorized approach O(n)
    # Pass 1: np.maximum.at already computed the max theta per bin (above)
    # Pass 2: Find points that equal the max for their bin, get their distances
    distances = np.zeros(num_bins, dtype=np.float64)

    # Find indices where each point equals the max for its bin
    is_max = theta_valid == skyline[bins]

    # Get first occurrence of max per bin (arbitrary tiebreaker)
    max_point_indices = np.where(is_max)[0]
    max_point_bins = bins[max_point_indices]

    # Use np.unique to find first occurrence per bin
    _, first_occurrence_idx = np.unique(max_point_bins, return_index=True)
    final_indices = max_point_indices[first_occurrence_idx]
    final_bins = max_point_bins[first_occurrence_idx]

    distances[final_bins] = rho_valid[final_indices]

    return skyline.astype(np.float32), distances.astype(np.float32)


def plot_skyline(skyline: np.ndarray, azimuth_resolution: float = 0.1, ax=None):
    """
    Plot panoramic skyline as polar plot.

    Args:
        skyline: Array of elevation angles from compute_panoramic_skyline
        azimuth_resolution: Angular resolution used to generate skyline
        ax: Optional matplotlib axes (creates new figure if None)

    Returns:
        matplotlib axes object
    """
    import matplotlib.pyplot as plt

    num_bins = len(skyline)
    azimuths = np.linspace(0, 360, num_bins, endpoint=False)
    azimuths_rad = np.radians(azimuths)

    if ax is None:
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})

    # Polar plot with 0° at top (North) and clockwise direction
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)

    # Plot skyline
    ax.plot(azimuths_rad, skyline, 'b-', linewidth=0.5)
    ax.fill(azimuths_rad, skyline, alpha=0.3)

    # Labels
    ax.set_xlabel('Azimuth')
    ax.set_title('Panoramic Skyline (elevation angle vs azimuth)')

    return ax


# --- Skyline Matching (Nagy 2020 §3.3) ---


def skyline_to_elevation(
    skyline_rows: np.ndarray,
    image_height: int,
    fov_v: float,
) -> np.ndarray:
    """
    Convert image skyline (pixel rows) to elevation angles.

    Assumes image center corresponds to 0° elevation (horizontal).

    Args:
        skyline_rows: Row indices from lie_05.dp_skyline() (-1 = invalid)
        image_height: Image height in pixels
        fov_v: Vertical field of view in degrees

    Returns:
        Elevation angles in degrees (NaN for invalid rows)
    """
    # Image center is assumed to be horizon (0° elevation)
    center_row = image_height / 2
    degrees_per_pixel = fov_v / image_height

    # Row 0 is top of image (positive elevation), row max is bottom (negative)
    elevations = (center_row - skyline_rows) * degrees_per_pixel

    # Mark invalid rows as NaN
    elevations = np.where(skyline_rows >= 0, elevations, np.nan)

    return elevations


def resample_skyline(
    skyline: np.ndarray,
    source_fov: float,
    target_resolution: float,
) -> np.ndarray:
    """
    Resample image skyline to match DEM panoramic skyline resolution.

    Nagy §3.3: "HFOV of the camera and the panoramic skyline need to be
    synchronized via the sampling rate of the two signals."

    Args:
        skyline: Image skyline elevation angles (one per column)
        source_fov: Horizontal FOV of the image in degrees
        target_resolution: Target angular resolution in degrees per sample

    Returns:
        Resampled skyline with target_resolution spacing
    """
    num_source = len(skyline)
    source_resolution = source_fov / num_source

    # Number of output samples
    num_target = int(np.ceil(source_fov / target_resolution))

    # Create output positions
    target_positions = np.arange(num_target) * target_resolution / source_resolution

    # Interpolate (use linear interpolation, handling NaN)
    valid_mask = ~np.isnan(skyline)
    if not valid_mask.any():
        return np.full(num_target, np.nan)

    # Simple linear interpolation
    source_positions = np.arange(num_source)
    resampled = np.interp(
        target_positions,
        source_positions[valid_mask],
        skyline[valid_mask],
        left=np.nan,
        right=np.nan,
    )

    return resampled


def match_skylines(
    dem_skyline: np.ndarray,
    image_skyline: np.ndarray,
    image_fov: float,
    azimuth_resolution: float = 0.1,
    search_center: float | None = None,
    search_window: float = 180.0,
) -> tuple[float, float, np.ndarray]:
    """
    Find best alignment via normalized cross-correlation.

    Nagy §3.3: "After calculating the cross-correlation between the two
    vectors, the maximum of the cross-correlation function indicates the
    point K where the signals are best aligned."

    Args:
        dem_skyline: Full 360° panoramic skyline from compute_panoramic_skyline
        image_skyline: Resampled image skyline (elevation angles, may have NaN)
        image_fov: Horizontal FOV of the image in degrees
        azimuth_resolution: Angular resolution of DEM skyline
        search_center: Center azimuth for search (None = search full 360°)
        search_window: Search ± this many degrees around center

    Returns:
        Tuple of (best_azimuth, correlation, correlation_curve):
        - best_azimuth: Azimuth of image center in degrees
        - correlation: Peak correlation value (0-1)
        - correlation_curve: Full correlation curve for diagnostics
    """
    num_dem = len(dem_skyline)
    num_image = len(image_skyline)

    # Determine search range
    if search_center is not None:
        # Search around specified center
        start_idx = int((search_center - search_window) / azimuth_resolution) % num_dem
        end_idx = int((search_center + search_window) / azimuth_resolution) % num_dem
        if start_idx < end_idx:
            search_indices = np.arange(start_idx, end_idx)
        else:
            # Wrap around 0°
            search_indices = np.concatenate([
                np.arange(start_idx, num_dem),
                np.arange(0, end_idx)
            ])
    else:
        search_indices = np.arange(num_dem)

    # Create mask for valid image samples
    valid_mask = ~np.isnan(image_skyline)
    if valid_mask.sum() < 10:
        raise ValueError("Too few valid image skyline samples for matching")

    # Normalize image skyline (zero mean, unit variance) for NCC
    image_valid = image_skyline[valid_mask]
    image_mean = np.mean(image_valid)
    image_std = np.std(image_valid)
    if image_std < 1e-6:
        raise ValueError("Image skyline has no variation")
    image_norm = (image_skyline - image_mean) / image_std
    image_norm = np.where(valid_mask, image_norm, 0)

    # Compute normalized cross-correlation at each position
    correlations = np.zeros(num_dem)
    half_width = num_image // 2

    for shift in search_indices:
        # Extract DEM window centered at this position
        # The shift represents where the image center would be
        start = (shift - half_width) % num_dem
        indices = [(start + i) % num_dem for i in range(num_image)]
        dem_window = dem_skyline[indices]

        # Normalize DEM window
        dem_valid = dem_window[valid_mask]
        dem_mean = np.mean(dem_valid)
        dem_std = np.std(dem_valid)
        if dem_std < 1e-6:
            continue
        dem_norm = (dem_window - dem_mean) / dem_std

        # Compute correlation only at valid positions
        corr = np.sum(image_norm[valid_mask] * dem_norm[valid_mask]) / valid_mask.sum()
        correlations[shift] = corr

    # Find best match
    best_idx = np.argmax(correlations)
    best_azimuth = best_idx * azimuth_resolution
    best_corr = correlations[best_idx]

    return best_azimuth, best_corr, correlations


def determine_azimuth(
    image_path: str,
    dem_dir: str = "dem",
    dem_resolution: str = "200cm",
    dem_radius: float = 10000,
    azimuth_resolution: float = 0.1,
    search_window: float = 45.0,
    apply_tilt: bool = True,
    verbose: bool = False,
) -> tuple[float, float, dict]:
    """
    Full pipeline: image → azimuth.

    Implements Nagy 2020 method: extract skyline from image, compute
    panoramic skyline from DEM, match via cross-correlation.

    Args:
        image_path: Path to geotagged image
        dem_dir: Directory containing DEM tiles
        dem_resolution: DEM resolution ("50cm" or "200cm")
        dem_radius: Radius in meters for DEM loading
        azimuth_resolution: Angular resolution in degrees
        search_window: Search ± this many degrees around compass heading
        apply_tilt: Whether to apply pitch/roll correction
        verbose: Print progress messages

    Returns:
        Tuple of (azimuth, correlation, debug_info):
        - azimuth: Computed azimuth of image center (degrees from true north)
        - correlation: Match quality (0-1)
        - debug_info: Dict with intermediate values for debugging
    """
    from utils import (
        extract_gps_from_image,
        gps_to_swiss,
        load_dem_tiles,
        extract_camera_params,
        apply_tilt_correction,
    )
    from lie_05 import load_image, detect_skyline

    debug = {}

    # 1. Extract camera parameters from EXIF
    if verbose:
        print(f"Reading EXIF from {image_path}...")
    params = extract_camera_params(image_path)
    debug["camera_params"] = params

    if params["fov_h"] is None:
        raise ValueError("No FOV found in EXIF data")

    # Compute vertical FOV from horizontal FOV and aspect ratio
    aspect = params["image_width"] / params["image_height"]
    fov_v = params["fov_h"] / aspect
    debug["fov_v"] = fov_v

    if verbose:
        print(f"  FOV: {params['fov_h']:.1f}° H × {fov_v:.1f}° V")
        print(f"  Compass heading: {params['compass_heading']:.1f}°")
        if params["pitch"] is not None:
            print(f"  Tilt: pitch={params['pitch']:.1f}°, roll={params['roll']:.1f}°")

    # 2. Get camera position
    lat, lon = extract_gps_from_image(image_path)
    cam_e, cam_n = gps_to_swiss(lat, lon)
    debug["position"] = {"lat": lat, "lon": lon, "easting": cam_e, "northing": cam_n}

    if verbose:
        print(f"Camera position: {lat:.6f}°N, {lon:.6f}°E")
        print(f"  Swiss coords: {cam_e:.1f} E, {cam_n:.1f} N")

    # 3. Load DEM and compute panoramic skyline
    if verbose:
        print(f"Loading DEM tiles ({dem_resolution}, {dem_radius/1000:.0f}km radius)...")
    grid, transform = load_dem_tiles(dem_dir, cam_e, cam_n, radius=dem_radius, resolution=dem_resolution)

    cam_z = get_camera_elevation(grid, transform, cam_e, cam_n)
    debug["camera_elevation"] = cam_z

    if verbose:
        print(f"Computing panoramic skyline...")
    dem_skyline = compute_panoramic_skyline(
        grid, transform, cam_e, cam_n, cam_z,
        azimuth_resolution=azimuth_resolution,
        max_distance=dem_radius,
    )
    debug["dem_skyline"] = dem_skyline

    if verbose:
        print(f"  DEM skyline: {len(dem_skyline)} samples, range [{dem_skyline.min():.1f}°, {dem_skyline.max():.1f}°]")

    # 4. Extract image skyline
    if verbose:
        print("Extracting image skyline...")
    image = load_image(image_path)
    skyline_rows, scale = detect_skyline(image)
    debug["image_skyline_rows"] = skyline_rows
    debug["image_scale"] = scale

    # Scale rows back to original image size
    skyline_rows_orig = (skyline_rows / scale).astype(int)
    skyline_rows_orig = np.where(skyline_rows >= 0, skyline_rows_orig, -1)

    valid_count = np.sum(skyline_rows >= 0)
    if verbose:
        print(f"  Image skyline: {valid_count}/{len(skyline_rows)} valid columns")

    # 5. Convert to elevation angles
    image_elevations = skyline_to_elevation(
        skyline_rows_orig,
        params["image_height"],
        fov_v,
    )
    debug["image_elevations"] = image_elevations

    # 6. Apply tilt correction to DEM skyline (if enabled)
    if apply_tilt and params["pitch"] is not None:
        if verbose:
            print(f"Applying tilt correction (pitch={params['pitch']:.1f}°, roll={params['roll']:.1f}°)...")
        azimuths = np.arange(len(dem_skyline)) * azimuth_resolution
        dem_skyline_corrected = apply_tilt_correction(
            dem_skyline,
            azimuths,
            params["compass_heading"] or 0,
            params["pitch"],
            params["roll"],
        )
        debug["dem_skyline_corrected"] = dem_skyline_corrected
    else:
        dem_skyline_corrected = dem_skyline

    # 7. Resample image skyline to match DEM resolution
    image_skyline_resampled = resample_skyline(
        image_elevations,
        params["fov_h"],
        azimuth_resolution,
    )
    debug["image_skyline_resampled"] = image_skyline_resampled

    if verbose:
        print(f"  Resampled image skyline: {len(image_skyline_resampled)} samples")

    # 8. Match skylines
    if verbose:
        search_center = params["compass_heading"]
        if search_center is not None:
            print(f"Matching skylines (searching ±{search_window}° around {search_center:.1f}°)...")
        else:
            print(f"Matching skylines (searching full 360°)...")

    azimuth, correlation, corr_curve = match_skylines(
        dem_skyline_corrected,
        image_skyline_resampled,
        params["fov_h"],
        azimuth_resolution=azimuth_resolution,
        search_center=params["compass_heading"],
        search_window=search_window,
    )
    debug["correlation_curve"] = corr_curve

    if verbose:
        print(f"\nResult:")
        print(f"  Computed azimuth: {azimuth:.2f}°")
        print(f"  Correlation: {correlation:.3f}")
        if params["compass_heading"] is not None:
            diff = azimuth - params["compass_heading"]
            if diff > 180:
                diff -= 360
            elif diff < -180:
                diff += 360
            print(f"  Difference from compass: {diff:+.2f}°")

    return azimuth, correlation, debug


if __name__ == "__main__":
    # Example usage with test location
    import argparse
    from utils import extract_gps_from_image, gps_to_swiss, load_dem_tiles

    parser = argparse.ArgumentParser(description="Generate panoramic skyline from DEM and match with image")
    parser.add_argument("image", help="Path to geotagged image")
    parser.add_argument("--dem-dir", default="dem", help="Directory containing DEM tiles")
    parser.add_argument("--radius", type=float, default=10000, help="Radius in meters (default: 10000)")
    parser.add_argument("--dem-resolution", choices=["50cm", "200cm"], default="200cm",
                        help="DEM resolution (default: 200cm for faster processing)")
    parser.add_argument("--height", type=float, default=2.0, help="Camera height above ground (default: 2.0)")
    parser.add_argument("--output", help="Output file for skyline plot (PNG)")
    parser.add_argument("--resolution", type=float, default=0.1, help="Azimuth resolution in degrees (default: 0.1)")
    parser.add_argument("--csv", help="Output CSV file for skyline data")
    parser.add_argument("--with-distances", action="store_true", help="Include distance data in output")

    # Matching options
    parser.add_argument("--match", action="store_true", help="Run full azimuth matching pipeline")
    parser.add_argument("--search-window", type=float, default=45.0, help="Search window ± degrees around compass (default: 45)")
    parser.add_argument("--no-tilt", action="store_true", help="Disable pitch/roll tilt correction")

    args = parser.parse_args()

    # If --match is specified, run the full pipeline
    if args.match:
        azimuth, correlation, debug = determine_azimuth(
            args.image,
            dem_dir=args.dem_dir,
            dem_resolution=args.dem_resolution,
            dem_radius=args.radius,
            azimuth_resolution=args.resolution,
            search_window=args.search_window,
            apply_tilt=not args.no_tilt,
            verbose=True,
        )

        # Optionally save debug plot
        if args.output:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            # 1. DEM skyline (polar)
            ax_polar = fig.add_subplot(2, 2, 1, projection='polar')
            plot_skyline(debug["dem_skyline"], args.resolution, ax_polar)
            ax_polar.set_title("DEM Panoramic Skyline")

            # 2. Correlation curve
            ax_corr = axes[0, 1]
            corr = debug["correlation_curve"]
            azimuths_full = np.arange(len(corr)) * args.resolution
            ax_corr.plot(azimuths_full, corr, 'b-', linewidth=0.5)
            ax_corr.axvline(azimuth, color='r', linestyle='--', label=f'Best: {azimuth:.1f}°')
            compass = debug["camera_params"]["compass_heading"]
            if compass is not None:
                ax_corr.axvline(compass, color='g', linestyle=':', label=f'Compass: {compass:.1f}°')
            ax_corr.set_xlabel('Azimuth (degrees)')
            ax_corr.set_ylabel('Correlation')
            ax_corr.set_xlim(0, 360)
            ax_corr.legend()
            ax_corr.set_title(f'Cross-correlation (peak={correlation:.3f})')
            ax_corr.grid(True, alpha=0.3)

            # 3. Matched skylines overlay
            ax_match = axes[1, 0]
            dem_sky = debug.get("dem_skyline_corrected", debug["dem_skyline"])
            img_sky = debug["image_skyline_resampled"]
            fov_h = debug["camera_params"]["fov_h"]
            num_img = len(img_sky)

            # Extract DEM window at best match position
            center_idx = int(azimuth / args.resolution)
            half_width = num_img // 2
            start = (center_idx - half_width) % len(dem_sky)
            indices = [(start + i) % len(dem_sky) for i in range(num_img)]
            dem_window = dem_sky[indices]

            x = np.linspace(-fov_h/2, fov_h/2, num_img)
            ax_match.plot(x, dem_window, 'b-', label='DEM skyline', linewidth=1)
            ax_match.plot(x, img_sky, 'r-', label='Image skyline', linewidth=1)
            ax_match.set_xlabel('Angle from center (degrees)')
            ax_match.set_ylabel('Elevation (degrees)')
            ax_match.legend()
            ax_match.set_title(f'Matched Skylines (azimuth={azimuth:.1f}°)')
            ax_match.grid(True, alpha=0.3)

            # 4. Info text
            ax_info = axes[1, 1]
            ax_info.axis('off')
            info_text = f"""
Azimuth Determination Result
============================
Computed azimuth: {azimuth:.2f}°
Correlation: {correlation:.3f}

Camera Parameters:
  FOV: {debug["camera_params"]["fov_h"]:.1f}° H × {debug["fov_v"]:.1f}° V
  Compass heading: {debug["camera_params"]["compass_heading"]:.1f}°
  Pitch: {debug["camera_params"]["pitch"]:.1f}°
  Roll: {debug["camera_params"]["roll"]:.1f}°

Position:
  {debug["position"]["lat"]:.6f}°N, {debug["position"]["lon"]:.6f}°E
  Elevation: {debug["camera_elevation"]:.1f}m
"""
            ax_info.text(0.1, 0.9, info_text, transform=ax_info.transAxes,
                        fontfamily='monospace', verticalalignment='top', fontsize=10)

            plt.tight_layout()
            plt.savefig(args.output, dpi=150)
            print(f"Saved debug plot to {args.output}")

        # Save CSV results
        if args.csv:
            import csv
            from pathlib import Path

            csv_path = Path(args.csv)
            file_exists = csv_path.exists()

            # Compute difference from compass
            compass = debug["camera_params"]["compass_heading"]
            if compass is not None:
                diff = azimuth - compass
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
            else:
                diff = None

            row = {
                "image": args.image,
                "computed_azimuth": f"{azimuth:.2f}",
                "compass_heading": f"{compass:.2f}" if compass else "",
                "difference": f"{diff:.2f}" if diff is not None else "",
                "correlation": f"{correlation:.3f}",
                "fov_h": f"{debug['camera_params']['fov_h']:.1f}",
                "fov_v": f"{debug['fov_v']:.1f}",
                "pitch": f"{debug['camera_params']['pitch']:.1f}" if debug['camera_params']['pitch'] else "",
                "roll": f"{debug['camera_params']['roll']:.1f}" if debug['camera_params']['roll'] else "",
                "lat": f"{debug['position']['lat']:.6f}",
                "lon": f"{debug['position']['lon']:.6f}",
                "elevation": f"{debug['camera_elevation']:.1f}",
            }

            with open(csv_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)

            print(f"Saved results to {args.csv}")

        exit(0)

    # Get camera position from image
    print(f"Reading GPS from {args.image}...")
    lat, lon = extract_gps_from_image(args.image)
    print(f"GPS: {lat:.6f}°N, {lon:.6f}°E")

    cam_e, cam_n = gps_to_swiss(lat, lon)
    print(f"Swiss coords: {cam_e:.1f} E, {cam_n:.1f} N")

    # Load DEM tiles
    print(f"Loading DEM tiles within {args.radius/1000:.1f}km radius ({args.dem_resolution} resolution)...")
    grid, transform = load_dem_tiles(args.dem_dir, cam_e, cam_n, radius=args.radius, resolution=args.dem_resolution)
    print(f"DEM grid size: {grid.shape} ({grid.shape[0] * grid.shape[1] / 1e6:.1f}M points)")

    # Get camera elevation
    cam_z = get_camera_elevation(grid, transform, cam_e, cam_n, args.height)
    print(f"Camera elevation: {cam_z:.1f}m (ground + {args.height}m)")

    # Compute panoramic skyline
    print("Computing panoramic skyline...")
    if args.with_distances or args.csv:
        skyline, distances = compute_panoramic_skyline(
            grid, transform, cam_e, cam_n, cam_z,
            azimuth_resolution=args.resolution,
            max_distance=args.radius,
            return_distances=True,
        )
    else:
        skyline = compute_panoramic_skyline(
            grid, transform, cam_e, cam_n, cam_z,
            azimuth_resolution=args.resolution,
            max_distance=args.radius,
        )
        distances = None
    print(f"Skyline: {len(skyline)} samples, elevation range [{skyline.min():.1f}°, {skyline.max():.1f}°]")

    # Save CSV if requested
    if args.csv:
        save_skyline_csv(args.csv, skyline, distances if args.with_distances else None, args.resolution)
        print(f"Saved CSV to {args.csv}")

    # Plot result
    if args.output:
        import matplotlib
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Polar plot
    ax_polar = fig.add_subplot(1, 2, 1, projection='polar')
    plot_skyline(skyline, args.resolution, ax_polar)

    # Linear plot
    azimuths = np.linspace(0, 360, len(skyline), endpoint=False)
    ax2.plot(azimuths, skyline, 'b-', linewidth=0.5)
    ax2.fill_between(azimuths, skyline, alpha=0.3)
    ax2.set_xlabel('Azimuth (degrees)')
    ax2.set_ylabel('Elevation angle (degrees)')
    ax2.set_xlim(0, 360)
    ax2.set_xticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
    ax2.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'])
    ax2.grid(True, alpha=0.3)
    ax2.set_title('Panoramic Skyline (linear)')

    plt.tight_layout()

    if args.output:
        plt.savefig(args.output, dpi=150)
        print(f"Saved plot to {args.output}")
    else:
        plt.show()
