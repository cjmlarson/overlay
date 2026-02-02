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


if __name__ == "__main__":
    # Example usage with test location
    import argparse
    from utils import extract_gps_from_image, gps_to_swiss, load_dem_tiles

    parser = argparse.ArgumentParser(description="Generate panoramic skyline from DEM")
    parser.add_argument("image", help="Path to geotagged image")
    parser.add_argument("--dem-dir", default="dem", help="Directory containing DEM tiles")
    parser.add_argument("--radius", type=float, default=10000, help="Radius in meters (default: 10000)")
    parser.add_argument("--height", type=float, default=2.0, help="Camera height above ground (default: 2.0)")
    parser.add_argument("--output", help="Output file for skyline plot (PNG)")
    parser.add_argument("--resolution", type=float, default=0.1, help="Azimuth resolution in degrees (default: 0.1)")
    parser.add_argument("--csv", help="Output CSV file for skyline data")
    parser.add_argument("--with-distances", action="store_true", help="Include distance data in output")

    args = parser.parse_args()

    # Get camera position from image
    print(f"Reading GPS from {args.image}...")
    lat, lon = extract_gps_from_image(args.image)
    print(f"GPS: {lat:.6f}°N, {lon:.6f}°E")

    cam_e, cam_n = gps_to_swiss(lat, lon)
    print(f"Swiss coords: {cam_e:.1f} E, {cam_n:.1f} N")

    # Load DEM tiles
    print(f"Loading DEM tiles within {args.radius/1000:.1f}km radius...")
    grid, transform = load_dem_tiles(args.dem_dir, cam_e, cam_n, radius=args.radius)
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
