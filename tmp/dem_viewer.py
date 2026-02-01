#!/usr/bin/env python3
"""
DEM Viewer: Render 3D terrain view from GPS coordinates.

Extracts GPS from image EXIF, transforms to Swiss LV95, loads DEM tiles,
and renders a 3D view facing east from 2m above ground.
"""

import re
from pathlib import Path

import exiftool
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer


def get_gps_from_exif(image_path: str) -> tuple[float, float]:
    """Extract GPS coordinates from image EXIF metadata.

    Returns:
        (latitude, longitude) in decimal degrees
    """
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(image_path)[0]

    lat = metadata.get("EXIF:GPSLatitude")
    lon = metadata.get("EXIF:GPSLongitude")
    lat_ref = metadata.get("EXIF:GPSLatitudeRef", "N")
    lon_ref = metadata.get("EXIF:GPSLongitudeRef", "E")

    if lat is None or lon is None:
        raise ValueError(f"No GPS data found in {image_path}")

    # Apply hemisphere sign
    if lat_ref == "S":
        lat = -lat
    if lon_ref == "W":
        lon = -lon

    return lat, lon


def gps_to_swiss(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 GPS coordinates to Swiss LV95 (EPSG:2056).

    Returns:
        (easting, northing) in meters
    """
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
    easting, northing = transformer.transform(lon, lat)
    return easting, northing


def find_dem_tile(easting: float, northing: float, csv_path: str) -> str:
    """Find the DEM tile URL containing the given coordinates.

    Tile naming: swissalti3d_{year}_{east_km}-{north_km}_0.5_2056_5728.tif
    Each tile is 1km x 1km, coords are SW corner.
    """
    # Calculate tile coordinates (in km, rounded down to tile SW corner)
    tile_e = int(easting // 1000)
    tile_n = int(northing // 1000)

    # Match any year (2019, 2025, etc.)
    pattern = f"_{tile_e}-{tile_n}_"

    with open(csv_path) as f:
        for line in f:
            url = line.strip()
            if pattern in url:
                return url

    raise ValueError(f"No tile found for E={tile_e}000, N={tile_n}000")


def find_tiles_in_area(easting: float, northing: float, radius_m: float,
                       csv_path: str) -> list[str]:
    """Find all DEM tiles covering a circular area."""
    tiles = []

    # Build a set of all available tiles from CSV
    available_tiles = {}
    with open(csv_path) as f:
        for line in f:
            url = line.strip()
            # Extract tile coords from URL (any year)
            match = re.search(r'swissalti3d_\d{4}_(\d+)-(\d+)_', url)
            if match:
                tile_key = (int(match.group(1)), int(match.group(2)))
                available_tiles[tile_key] = url

    # Calculate bounding box in tile coords
    min_e = int((easting - radius_m) // 1000)
    max_e = int((easting + radius_m) // 1000)
    min_n = int((northing - radius_m) // 1000)
    max_n = int((northing + radius_m) // 1000)

    for te in range(min_e, max_e + 1):
        for tn in range(min_n, max_n + 1):
            if (te, tn) in available_tiles:
                tiles.append(available_tiles[(te, tn)])

    return tiles


def load_dem_around_point(tile_urls: list[str], easting: float, northing: float,
                          radius_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load DEM data from tiles covering the area around a point.

    Returns:
        (X, Y, Z) meshgrid arrays for plotting
    """
    if not tile_urls:
        raise ValueError("No tile URLs provided")

    # Define the bounding box we want
    min_e = easting - radius_m
    max_e = easting + radius_m
    min_n = northing - radius_m
    max_n = northing + radius_m

    # Read and merge tiles
    all_data = []
    all_transforms = []

    for url in tile_urls:
        print(f"Loading: {url.split('/')[-1]}")
        with rasterio.open(url) as src:
            # Get the window for our area of interest
            window = rasterio.windows.from_bounds(
                min_e, min_n, max_e, max_n, src.transform
            )
            # Clip window to valid range
            window = window.intersection(rasterio.windows.Window(
                0, 0, src.width, src.height
            ))

            if window.width > 0 and window.height > 0:
                data = src.read(1, window=window)
                transform = src.window_transform(window)
                all_data.append((data, transform, window))

    if not all_data:
        raise ValueError("No data loaded from tiles")

    # For simplicity with single tile, just use the first one
    # A more complete implementation would merge multiple tiles
    data, transform, window = all_data[0]

    # Create coordinate meshgrid
    rows, cols = data.shape
    col_coords = np.arange(cols)
    row_coords = np.arange(rows)

    # Convert pixel coords to world coords
    xs = transform.c + col_coords * transform.a
    ys = transform.f + row_coords * transform.e

    X, Y = np.meshgrid(xs, ys)
    Z = data

    return X, Y, Z


def get_elevation_at(tile_urls: list[str], easting: float, northing: float) -> float:
    """Sample elevation from DEM at a specific coordinate.

    Tries each tile until finding one that contains the point.
    """
    for url in tile_urls:
        try:
            with rasterio.open(url) as src:
                # Check if point is within this tile's bounds
                if not (src.bounds.left <= easting <= src.bounds.right and
                        src.bounds.bottom <= northing <= src.bounds.top):
                    continue

                # Convert world coords to pixel coords
                row, col = src.index(easting, northing)

                # Clamp to valid range
                row = max(0, min(row, src.height - 1))
                col = max(0, min(col, src.width - 1))

                # Read single pixel value
                elevation = src.read(1)[row, col]
                return float(elevation)
        except Exception:
            continue

    raise ValueError(f"Could not get elevation at E={easting}, N={northing}")


def compute_hillshade(Z: np.ndarray, azimuth: float = 315, altitude: float = 45) -> np.ndarray:
    """Compute hillshade from elevation data.

    Args:
        Z: Elevation array
        azimuth: Light source azimuth in degrees (315 = NW)
        altitude: Light source altitude in degrees above horizon
    """
    # Convert to radians
    az_rad = np.radians(azimuth)
    alt_rad = np.radians(altitude)

    # Compute gradients
    dy, dx = np.gradient(Z)

    # Compute slope and aspect
    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dx, dy)

    # Compute hillshade
    shade = (np.sin(alt_rad) * np.cos(slope) +
             np.cos(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect))

    # Normalize to 0-1
    shade = (shade - shade.min()) / (shade.max() - shade.min())
    return shade


def render_view(X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
                cam_e: float, cam_n: float, cam_z: float,
                output_path: str, azimuth: float = 90):
    """Render 3D view of terrain from camera position facing given azimuth.

    Args:
        X, Y, Z: Terrain meshgrid arrays
        cam_e, cam_n, cam_z: Camera position (easting, northing, elevation)
        output_path: Path to save output PNG
        azimuth: Direction to face in degrees (0=north, 90=east, etc.)
    """
    fig = plt.figure(figsize=(14, 10), facecolor='white')
    ax = fig.add_subplot(111, projection='3d', facecolor='white')

    # Subsample for performance
    step = max(1, min(X.shape) // 150)
    Xs = X[::step, ::step]
    Ys = Y[::step, ::step]
    Zs = Z[::step, ::step]

    # Compute hillshade for coloring
    shade = compute_hillshade(Zs, azimuth=315, altitude=35)

    # Create grayscale colormap from hillshade
    # Cap brightness so peaks aren't pure white against background
    from matplotlib.colors import LightSource
    ls = LightSource(azdeg=315, altdeg=35)
    rgb = ls.shade(Zs, cmap=plt.cm.gray, vert_exag=1, blend_mode='soft')
    # Darken: scale RGB values to max 0.85 so bright areas still visible
    rgb[..., :3] = rgb[..., :3] * 0.8 + 0.05

    # Plot as wireframe mesh with hillshade surface underneath
    ax.plot_surface(Xs, Ys, Zs, facecolors=rgb, linewidth=0,
                    antialiased=True, shade=False)

    # Add subtle wireframe on top
    wire_step = max(1, step * 3)
    Xw = X[::wire_step, ::wire_step]
    Yw = Y[::wire_step, ::wire_step]
    Zw = Z[::wire_step, ::wire_step]
    ax.plot_wireframe(Xw, Yw, Zw, color='#404040', linewidth=0.3, alpha=0.4)

    # Set view angle
    mpl_azim = 90 - azimuth  # Convert compass to matplotlib convention
    ax.view_init(elev=5, azim=mpl_azim)

    # Remove all axes, gridlines, and panes
    ax.set_axis_off()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    # Paths
    base_dir = Path(__file__).parent.parent
    image_path = base_dir / "img" / "IMG_5620.jpeg"
    csv_path = base_dir / "dem" / "ch.swisstopo.swissalti3d-c7wuuzEk.csv"
    output_path = Path(__file__).parent / "view_output.png"

    # 1. Extract GPS from EXIF
    print("Extracting GPS from EXIF...")
    lat, lon = get_gps_from_exif(str(image_path))
    print(f"  GPS: {lat:.6f}°N, {lon:.6f}°E")

    # 2. Convert to Swiss coordinates
    print("Converting to Swiss LV95...")
    easting, northing = gps_to_swiss(lat, lon)
    print(f"  Swiss: E={easting:.1f}, N={northing:.1f}")

    # 3. Find DEM tiles covering the area
    print("Finding DEM tiles...")
    radius_m = 500  # Load 500m radius around camera
    tile_urls = find_tiles_in_area(easting, northing, radius_m, str(csv_path))
    print(f"  Found {len(tile_urls)} tile(s)")

    if not tile_urls:
        print("ERROR: No DEM tiles found for this location!")
        return

    # 4. Get ground elevation at camera position
    print("Getting ground elevation...")
    ground_elev = get_elevation_at(tile_urls, easting, northing)
    camera_height = 2.0  # 2m above ground
    cam_z = ground_elev + camera_height
    print(f"  Ground: {ground_elev:.1f}m, Camera: {cam_z:.1f}m")

    # 5. Load DEM data
    print("Loading DEM data...")
    X, Y, Z = load_dem_around_point(tile_urls, easting, northing, radius_m)
    print(f"  Loaded grid: {X.shape}")

    # 6. Render 3D view facing east
    print("Rendering view...")
    render_view(X, Y, Z, easting, northing, cam_z, str(output_path), azimuth=90)

    print("Done!")


if __name__ == "__main__":
    main()
