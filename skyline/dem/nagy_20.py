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
from numba import njit, prange
from scipy.signal import correlate


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
    from dem.utils import sample_elevation

    ground_z = sample_elevation(grid, transform, cam_e, cam_n)
    if np.isnan(ground_z):
        raise ValueError(f"Camera position ({cam_e}, {cam_n}) is outside DEM coverage")

    return ground_z + height_above_ground


# Maximum terrain elevation in meters (above Mont Blanc at 4808m)
MAX_TERRAIN_ELEVATION = 5000.0


@njit(cache=True, parallel=True)
def _ray_march_skyline(
    grid: np.ndarray,
    cam_row: float,
    cam_col: float,
    cam_z: float,
    cell_size: float,
    num_bins: int,
    max_distance: float,
    min_distance: float,
    distance_step: float,
    azimuth_start: float = 0.0,
    azimuth_end: float = 360.0,
    use_occlusion_culling: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Numba JIT-compiled ray-marching skyline computation.

    For each azimuth bin, march a ray outward from camera and sample DEM.
    Track maximum elevation angle encountered.

    Args:
        grid: DEM elevation grid
        cam_row, cam_col: Camera position in pixel coordinates
        cam_z: Camera elevation in meters
        cell_size: Meters per pixel
        num_bins: Number of azimuth bins for full 360°
        max_distance: Maximum ray distance in meters
        min_distance: Minimum ray distance in meters
        distance_step: Step size in meters
        azimuth_start: Start azimuth in degrees (default 0)
        azimuth_end: End azimuth in degrees (default 360)
        use_occlusion_culling: Enable early ray termination (default True)

    Returns:
        Tuple of (skyline, distances) arrays
    """
    h, w = grid.shape
    azimuth_resolution = 360.0 / num_bins
    num_steps = int((max_distance - min_distance) / distance_step) + 1

    # Determine which bins to compute
    start_bin = int(azimuth_start / azimuth_resolution)
    end_bin = int(azimuth_end / azimuth_resolution)
    if end_bin <= start_bin:
        end_bin += num_bins  # Handle wrap-around

    # Output arrays for full 360° (sparse if using range)
    skyline = np.zeros(num_bins, dtype=np.float64)
    distances = np.zeros(num_bins, dtype=np.float64)

    # Height ceiling for occlusion culling
    max_terrain_dz = MAX_TERRAIN_ELEVATION - cam_z

    # Parallel over azimuth bins in range
    for i in prange(end_bin - start_bin):
        bin_idx = (start_bin + i) % num_bins
        azimuth_deg = bin_idx * azimuth_resolution
        azimuth_rad = np.radians(azimuth_deg)

        # Direction vector (North = 0°, East = 90°)
        # sin(az) = East component, cos(az) = North component
        dir_e = np.sin(azimuth_rad)
        dir_n = np.cos(azimuth_rad)

        # Convert to pixel deltas per meter
        # cell_size is meters per pixel (negative for northing in Swiss coords)
        dir_col = dir_e / cell_size  # easting increases with column
        dir_row = -dir_n / cell_size  # northing decreases with row (negative cell_size_y)

        max_elev = 0.0
        max_dist = 0.0

        # March along ray
        for step in range(num_steps):
            dist = min_distance + step * distance_step

            # Occlusion culling: check if remaining distance can possibly beat current max
            if use_occlusion_culling and max_elev > 0.0:
                # Maximum possible elevation angle from remaining terrain
                max_possible_elev = np.degrees(np.arctan2(max_terrain_dz, dist))
                if max_possible_elev < max_elev:
                    # No point continuing - distant terrain can't exceed current skyline
                    break

            # Position along ray in pixel coordinates
            col = cam_col + dist * dir_col
            row = cam_row + dist * dir_row

            # Bounds check
            if col < 0 or col >= w - 1 or row < 0 or row >= h - 1:
                continue

            # Bilinear interpolation
            c0 = int(col)
            r0 = int(row)
            dc = col - c0
            dr = row - r0

            z00 = grid[r0, c0]
            z01 = grid[r0, c0 + 1]
            z10 = grid[r0 + 1, c0]
            z11 = grid[r0 + 1, c0 + 1]

            # Check for NaN (nodata)
            if np.isnan(z00) or np.isnan(z01) or np.isnan(z10) or np.isnan(z11):
                continue

            z = z00 * (1 - dc) * (1 - dr) + z01 * dc * (1 - dr) + z10 * (1 - dc) * dr + z11 * dc * dr

            # Elevation angle
            dz = z - cam_z
            elev_rad = np.arctan2(dz, dist)
            elev_deg = np.degrees(elev_rad)

            if elev_deg > max_elev:
                max_elev = elev_deg
                max_dist = dist

        skyline[bin_idx] = max_elev
        distances[bin_idx] = max_dist

    return skyline, distances


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
    azimuth_start: float | None = None,
    azimuth_end: float | None = None,
    use_occlusion_culling: bool = True,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """
    Compute 360° panoramic skyline from DEM using ray-marching.

    Uses ray-marching approach: for each azimuth, march outward from camera
    sampling the DEM and tracking maximum elevation angle. This is O(azimuths × steps)
    instead of O(grid_points), providing ~30x speedup for large DEMs.

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
        azimuth_start: Start of azimuth range to compute (None = 0°)
        azimuth_end: End of azimuth range to compute (None = 360°)
        use_occlusion_culling: Enable early ray termination optimization (default True)

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
    num_bins = int(360 / azimuth_resolution)

    # Convert camera position to pixel coordinates
    inv_transform = ~transform
    cam_col, cam_row = inv_transform * (cam_e, cam_n)

    # Get cell size (meters per pixel)
    cell_size = transform.a  # Assumes square pixels, takes x resolution

    # Distance step: use cell size to ensure we don't skip pixels
    # At far distances, we can use larger steps since angular resolution decreases
    distance_step = cell_size * 1.5  # Slightly larger than pixel size

    # Ensure grid is float32 for numba
    grid_f32 = grid.astype(np.float32) if grid.dtype != np.float32 else grid

    # Default to full 360° if not specified
    az_start = azimuth_start if azimuth_start is not None else 0.0
    az_end = azimuth_end if azimuth_end is not None else 360.0

    skyline, distances = _ray_march_skyline(
        grid_f32,
        float(cam_row),
        float(cam_col),
        float(cam_z),
        float(cell_size),
        num_bins,
        float(max_distance),
        float(min_distance),
        float(distance_step),
        float(az_start),
        float(az_end),
        use_occlusion_culling,
    )

    # Clip negative values to 0 (horizon extends beyond DEM coverage)
    skyline = np.maximum(skyline, 0)

    if return_distances:
        return skyline.astype(np.float32), distances.astype(np.float32)
    return skyline.astype(np.float32)


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
    Find best alignment via normalized cross-correlation using FFT.

    Nagy §3.3: "After calculating the cross-correlation between the two
    vectors, the maximum of the cross-correlation function indicates the
    point K where the signals are best aligned."

    Uses FFT-based correlation for O(N log N) complexity instead of O(N*M).

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
    half_width = num_image // 2

    # Create mask for valid image samples
    valid_mask = ~np.isnan(image_skyline)
    num_valid = valid_mask.sum()
    if num_valid < 10:
        raise ValueError("Too few valid image skyline samples for matching")

    # Normalize image skyline (zero mean, unit variance) for NCC
    image_valid = image_skyline[valid_mask]
    image_mean = np.mean(image_valid)
    image_std = np.std(image_valid)
    if image_std < 1e-6:
        raise ValueError("Image skyline has no variation")

    # Create normalized image template (NaN -> 0)
    image_norm = np.where(valid_mask, (image_skyline - image_mean) / image_std, 0.0)

    # Create a mask template (1 where valid, 0 where NaN)
    mask_template = valid_mask.astype(np.float64)

    # For circular correlation, tile the DEM skyline to handle wrap-around
    # Tile once: [dem | dem] so we can extract any window
    dem_tiled = np.concatenate([dem_skyline, dem_skyline])

    # Compute correlation at all positions using FFT
    # For each shift k, we need: sum(image_norm[i] * dem_norm_k[i]) / num_valid
    # where dem_norm_k is the normalized DEM window centered at k

    # Pre-compute sliding window statistics for DEM normalization
    # Using convolution to compute local mean and variance
    correlations = np.zeros(num_dem, dtype=np.float64)

    # FFT-based cross-correlation: correlate(dem_tiled, image_norm[::-1])
    # This gives us the unnormalized correlation at each shift
    raw_corr = correlate(dem_tiled, image_norm[::-1], mode='valid', method='fft')

    # Also compute sum of dem values in each window (for mean)
    dem_sum = correlate(dem_tiled, mask_template[::-1], mode='valid', method='fft')

    # Compute sum of dem^2 in each window (for std)
    dem_sq_sum = correlate(dem_tiled**2, mask_template[::-1], mode='valid', method='fft')

    # For each position, compute normalized correlation
    # dem_mean = dem_sum / num_valid
    # dem_var = dem_sq_sum / num_valid - dem_mean^2
    # correlation = (raw_corr - num_valid * image_mean/image_std * dem_mean) / (num_valid * dem_std)
    # Simplified: correlation = (raw_corr - dem_sum * (image_mean/image_std)) / sqrt(num_valid * dem_var)

    # Note: image is already normalized, so:
    # corr = sum(image_norm * dem) / num_valid
    # We want: sum(image_norm * dem_norm) / num_valid
    # = sum(image_norm * (dem - dem_mean)/dem_std) / num_valid
    # = (sum(image_norm * dem) - dem_mean * sum(image_norm)) / (num_valid * dem_std)
    # Since sum(image_norm * mask) = sum of image_norm at valid positions
    # = image_std normalized sum, which for zero-mean image is 0

    # Actually: sum(image_norm[valid]) = 0 by construction (zero mean)
    # So: corr = sum(image_norm * dem) / (num_valid * dem_std)
    #          = raw_corr / (num_valid * dem_std)

    # Compute dem std for each window
    dem_mean = dem_sum / num_valid
    dem_var = dem_sq_sum / num_valid - dem_mean**2
    dem_var = np.maximum(dem_var, 1e-12)  # Avoid division by zero
    dem_std_arr = np.sqrt(dem_var)

    # The correlation result is offset - we want position k to correspond to
    # image center at azimuth k, not image start at azimuth k
    # raw_corr[i] corresponds to image starting at position i in dem_tiled

    # Compute normalized correlation
    # raw_corr contains sum(image_norm * dem_window) for each window position
    ncc = raw_corr / (num_valid * dem_std_arr)

    # Extract the valid range (first num_dem positions correspond to one full cycle)
    # Position i in ncc = image starting at position i
    # We want: image CENTER at position k => image starts at position (k - half_width)
    # So: correlations[k] = ncc[k - half_width] = ncc[(k - half_width) % num_dem]

    for k in range(num_dem):
        start_pos = (k - half_width) % num_dem
        correlations[k] = ncc[start_pos]

    # Apply search window constraint
    if search_center is not None:
        # Zero out correlations outside search window
        center_idx = int(search_center / azimuth_resolution) % num_dem
        window_bins = int(search_window / azimuth_resolution)

        mask = np.zeros(num_dem, dtype=bool)
        for i in range(-window_bins, window_bins + 1):
            mask[(center_idx + i) % num_dem] = True
        correlations = np.where(mask, correlations, -np.inf)

    # Find best match
    best_idx = np.argmax(correlations)
    best_azimuth = best_idx * azimuth_resolution
    best_corr = correlations[best_idx]

    # Replace -inf with 0 for return value
    correlations = np.where(np.isinf(correlations), 0.0, correlations)

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
    skyline_method: str = "lie",
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
        skyline_method: Image skyline detection method ("lie" or "nagy")

    Returns:
        Tuple of (azimuth, correlation, debug_info):
        - azimuth: Computed azimuth of image center (degrees from true north)
        - correlation: Match quality (0-1)
        - debug_info: Dict with intermediate values for debugging
    """
    from dem.utils import (
        extract_gps_from_image,
        gps_to_swiss,
        load_dem_tiles,
        extract_camera_params,
        apply_tilt_correction,
    )
    if skyline_method == "nagy":
        from skyline.image.nagy_20 import load_image, detect_skyline
    else:
        from skyline.image.lie_05 import load_image, detect_skyline

    debug = {}
    debug["skyline_method"] = skyline_method

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
    # Use compass heading to enable wedge loading optimization
    compass = params["compass_heading"]

    # Calculate wedge parameters for optimization
    # We need enough azimuth range to cover the search window + half the image FOV
    # on each side to ensure proper correlation matching
    fov_half = params["fov_h"] / 2 if params["fov_h"] else 45.0
    wedge_window = search_window + fov_half + 5.0  # Extra buffer for safety

    if verbose:
        if compass is not None:
            print(f"Loading DEM tiles ({dem_resolution}, {dem_radius/1000:.0f}km radius, wedge ±{wedge_window:.0f}°)...")
        else:
            print(f"Loading DEM tiles ({dem_resolution}, {dem_radius/1000:.0f}km radius)...")

    grid, transform = load_dem_tiles(
        dem_dir, cam_e, cam_n, radius=dem_radius, resolution=dem_resolution,
        azimuth_center=compass,
        azimuth_window=wedge_window,
    )

    cam_z = get_camera_elevation(grid, transform, cam_e, cam_n)
    debug["camera_elevation"] = cam_z

    # Calculate azimuth range for skyline computation
    if compass is not None:
        az_start = (compass - wedge_window) % 360
        az_end = (compass + wedge_window) % 360
    else:
        az_start = 0.0
        az_end = 360.0

    if verbose:
        if compass is not None:
            print(f"Computing panoramic skyline ({az_start:.0f}° to {az_end:.0f}°)...")
        else:
            print(f"Computing panoramic skyline...")

    dem_skyline = compute_panoramic_skyline(
        grid, transform, cam_e, cam_n, cam_z,
        azimuth_resolution=azimuth_resolution,
        max_distance=dem_radius,
        azimuth_start=az_start,
        azimuth_end=az_end,
        use_occlusion_culling=True,
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
    from dem.utils import extract_gps_from_image, gps_to_swiss, load_dem_tiles

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
