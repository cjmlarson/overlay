#!/usr/bin/env python3
"""
Orientation Optimization for Skyline Matching

Extends Nagy 2020 azimuth matching with roll and pitch optimization:
- Roll: Brent's method optimization to maximize correlation
- Pitch: Closed-form alignment for visual match

This is custom work, not from the Nagy paper.
"""

import numpy as np
from scipy.optimize import minimize_scalar

from dem.utils import apply_tilt_correction


def optimize_roll(
    dem_skyline: np.ndarray,
    image_skyline: np.ndarray,
    fixed_azimuth: float,
    compass_heading: float,
    pitch: float,
    roll_init: float,
    roll_range: float = 5.0,
    azimuth_resolution: float = 0.1,
) -> tuple[float, float]:
    """
    Find optimal roll that maximizes skyline correlation at a FIXED azimuth.

    Uses Brent's method for efficient 1D optimization (~10-15 evaluations).

    Args:
        dem_skyline: Full 360° panoramic DEM skyline (elevation angles)
        image_skyline: Resampled image skyline (elevation angles, may have NaN)
        fixed_azimuth: Azimuth determined by FFT matching (held constant)
        compass_heading: Center azimuth for tilt correction
        pitch: Pitch value (from accelerometer)
        roll_init: Initial roll from accelerometer
        roll_range: Search ± this many degrees (default 5.0)
        azimuth_resolution: Angular resolution of DEM skyline (default 0.1)

    Returns:
        Tuple of (optimal_roll, best_correlation)
    """
    num_dem = len(dem_skyline)
    num_image = len(image_skyline)
    azimuths = np.arange(num_dem) * azimuth_resolution

    # Precompute indices for extracting DEM window at fixed azimuth
    center_idx = int(fixed_azimuth / azimuth_resolution) % num_dem
    half_width = num_image // 2
    indices = (np.arange(num_image) + center_idx - half_width) % num_dem

    # Precompute valid mask and normalized image skyline
    valid = ~np.isnan(image_skyline)
    num_valid = valid.sum()
    if num_valid < 10:
        return roll_init, 0.0

    img_valid = image_skyline[valid]
    img_mean = img_valid.mean()
    img_std = img_valid.std()
    if img_std < 1e-6:
        return roll_init, 0.0

    # Create full-length normalized image array (zeros at invalid positions)
    # This matches how match_skylines handles NaN values
    image_norm_full = np.zeros(num_image, dtype=np.float64)
    image_norm_full[valid] = (img_valid - img_mean) / img_std

    # CRITICAL: In match_skylines, the FFT correlation uses reversed templates.
    # correlate(dem, image_norm[::-1]) and correlate(dem, mask[::-1]) means
    # the valid positions are effectively reversed in the correlation.
    #
    # For our manual computation to match, we need to use:
    # - dem_window[j] * image_norm[num_image-1-j] for the correlation
    # - mask[num_image-1-j] to determine valid positions for DEM statistics
    #
    # The simplest way to match this is to:
    # 1. Reverse the valid mask for DEM statistics
    # 2. Compute the correlation as sum(dem_window * image_norm[::-1])

    # Pre-compute the reversed mask for DEM statistics
    mask_reversed = valid[::-1]

    def neg_correlation(roll: float) -> float:
        """Compute negative correlation for minimization."""
        # Apply tilt correction to full DEM skyline
        corrected = apply_tilt_correction(
            dem_skyline, azimuths, compass_heading, pitch, roll
        )
        # Extract window at fixed azimuth
        dem_window = corrected[indices]

        # Compute DEM statistics at reversed valid positions (matching FFT behavior)
        # The FFT correlation uses mask[::-1], so DEM statistics are computed at
        # positions where valid[num_image-1-j] = True, which is mask_reversed[j] = True
        dem_valid_fft = dem_window[mask_reversed]
        dem_mean = dem_valid_fft.mean()
        dem_std = dem_valid_fft.std()
        if dem_std < 1e-6:
            return 0.0

        # Compute correlation matching FFT: sum(dem_window * image_norm[::-1])
        # normalized by num_valid * dem_std
        raw_corr = np.sum(dem_window * image_norm_full[::-1])
        corr = raw_corr / (num_valid * dem_std)
        return -corr  # Negative for minimization

    # Compute initial correlation for comparison
    init_neg_corr = neg_correlation(roll_init)
    init_corr = -init_neg_corr

    result = minimize_scalar(
        neg_correlation,
        bounds=(roll_init - roll_range, roll_init + roll_range),
        method='bounded',
        options={'xatol': 0.1}  # 0.1° tolerance
    )

    opt_corr = -result.fun

    # Only return optimized value if it actually improved
    if opt_corr > init_corr:
        return result.x, opt_corr
    else:
        # Optimization didn't help, return initial values
        return roll_init, init_corr


def compute_optimal_pitch(
    dem_skyline: np.ndarray,
    image_skyline: np.ndarray,
    best_azimuth: float,
    azimuth_resolution: float = 0.1,
) -> float:
    """
    Compute optimal pitch for visual alignment (closed-form).

    After azimuth and roll are optimized, pitch is simply the mean difference
    between image and DEM elevations at the matched position. This aligns
    the skylines vertically for visualization.

    Note: Pitch doesn't affect NCC (normalized away as DC offset), but
    it improves visual alignment in overlay displays.

    Args:
        dem_skyline: Full 360° panoramic DEM skyline (after tilt correction)
        image_skyline: Resampled image skyline (elevation angles)
        best_azimuth: Matched azimuth in degrees
        azimuth_resolution: Angular resolution of DEM skyline (default 0.1)

    Returns:
        Optimal pitch offset in degrees (add to current pitch)
    """
    num_dem = len(dem_skyline)
    num_image = len(image_skyline)

    # Find DEM window corresponding to matched azimuth
    center_idx = int(best_azimuth / azimuth_resolution) % num_dem
    half_width = num_image // 2

    # Extract DEM window (handle wrap-around)
    indices = (np.arange(num_image) + center_idx - half_width) % num_dem
    dem_window = dem_skyline[indices]

    # Compute mean difference (only for valid image samples)
    valid_mask = ~np.isnan(image_skyline)
    if valid_mask.sum() < 10:
        return 0.0

    pitch_offset = np.mean(image_skyline[valid_mask]) - np.mean(dem_window[valid_mask])
    return pitch_offset
