# Position Refinement: Particle Swarm Optimization (PSO)

## Problem Statement

We have a working skyline matching pipeline that estimates camera orientation (azimuth, roll, pitch) from geotagged mountain photos. The orientation matching works well (correlations ~0.96-0.97), but we observe **local shape discrepancies** between the image skyline and DEM-rendered skyline that indicate **camera position error** from GPS noise.

### The Single vs Double Peak Problem

In our test image (`IMG_5620.jpeg`), we observe a clear diagnostic signal:
- **Image skyline**: Shows a **single peak** for the main summit
- **DEM skyline**: Shows a **double peak** structure at the same location

This mismatch is caused by **parallax from position error**. The DEM skyline is rendered from the GPS coordinates, but the actual camera position was slightly different. Because the foreground peak is close to the camera, even a small position offset (tens of meters) causes:
- Different occlusion of background features
- Different apparent shape of the ridge crest

The correlation is still high because the *overall* skyline matches globally, but the *local peak structure* differs in the near-field. The closer the feature, the more sensitive it is to position error.

### Why Particle Swarm Optimization?

PSO is a **population-based stochastic optimizer** that:
1. **Explores globally**: Particles search the entire space, avoiding local minima
2. **Shares information**: Swarm converges toward best-known positions
3. **Handles non-convex objectives**: Robust to multiple local optima
4. **Cited in literature**: Porzi et al. 2014 used "Accelerated PSO" for exactly this problem
5. **Parallelizable**: Each particle's evaluation is independent

## Literature Review

### Porzi et al. 2014 - APSO for Camera Pose Registration

**Reference**: Porzi, L., Rota Bulò, S., Riemenschneider, H., & Kontschieder, P. (2014). "Learning contour-based registration for mountain peak detection."

**Section 3.3 - Optimization** (p. 5):
> "Accelerated Particle Swarm Optimization (APSO): Used to solve the registration optimization problem."

> "Bounded search space: Optimization constrained to a neighborhood around the sensor-based initial estimate using lower/upper bounds."

> "Objective function: Maximizes alignment score between detected contours and synthetic profiles, weighted by distance to observer... Non-linear objective with many local maxima, necessitating stochastic optimization."

**Key insight**: They explicitly chose PSO because the objective has "many local maxima" - exactly what we might face with skyline matching across position space.

### Brejcha et al. 2020 - Handling Large Position Uncertainty

**Reference**: Brejcha, J., et al. (2020). "LandscapeAR: Large Scale Outdoor Augmented Reality by Matching Photographs with Terrain Models Using Learned Descriptors."

**Section 4.2 - Robustness Analysis** (p. 12):
> "Tests registration with synthetic reference panoramas offset by Gaussian noise N(0m, 1000m)... Shows method improves localization beyond ~200m baseline error... Crossover point (~700m) identifies maximum useful baseline for refinement."

**Key insight**: Their method handles GPS errors of 200-700m. For our smaller errors (~50-100m), PSO should work well within a bounded region.

### Fedorov et al. 2016 - Multi-Stage with Local Search

**Reference**: Fedorov, R., Frajberg, D., & Fraternali, P. (2016). "A framework for outdoor mobile augmented reality and its application to mountain peak detection."

**Section 4.2 - Local Alignment**:
> "Local Alignment: Fine-tunes individual peak positions within local neighborhoods around globally-aligned locations (7.5° radius)."

**Key insight**: Local refinement in bounded regions is effective. PSO naturally handles bounded search with `lb` and `ub` parameters.

### PSO Algorithm Background

**Original**: Kennedy & Eberhart (1995), "Particle swarm optimization"

**Core idea**:
- Population of particles, each with position and velocity
- Each particle remembers its personal best position
- Swarm tracks global best position
- Velocity update: `v = w*v + c1*r1*(pbest - x) + c2*r2*(gbest - x)`
- Position update: `x = x + v`

**Parameters**:
- `w`: Inertia weight (exploration vs exploitation)
- `c1`: Cognitive parameter (personal best attraction)
- `c2`: Social parameter (global best attraction)
- `n_particles`: Swarm size (typically 20-50)

## Implementation Plan

### Phase 1: Objective Function

Same as Nelder-Mead - define function to minimize:
```python
def objective(position, image_skyline, dem_loader, orientation_params):
    """
    Compute negative correlation for a candidate position.
    PSO will call this for each particle at each iteration.
    """
    # 1. Convert position offset to lat/lon
    # 2. Render DEM skyline at this position
    # 3. Optimize orientation (azimuth, roll, pitch)
    # 4. Compute correlation
    # 5. Return negative correlation (PSO minimizes)
```

### Phase 2: PSO Setup

Using `pyswarm` library:
```python
from pyswarm import pso

# Search bounds: ±100m around GPS
lb = [-100, -100]  # Lower bounds [dx, dy]
ub = [100, 100]    # Upper bounds [dx, dy]

xopt, fopt = pso(
    func=objective,
    lb=lb,
    ub=ub,
    args=(image_skyline, dem_loader, orientation_params),
    swarmsize=30,
    maxiter=50,
    minstep=1.0,      # Minimum step size (meters)
    minfunc=0.001,    # Minimum improvement
    debug=True,
)
```

Alternative using `scipy.optimize.differential_evolution` (similar global optimizer):
```python
from scipy.optimize import differential_evolution

bounds = [(-100, 100), (-100, 100)]  # [dx, dy] bounds

result = differential_evolution(
    func=objective,
    bounds=bounds,
    args=(image_skyline, dem_loader, orientation_params),
    maxiter=50,
    workers=-1,  # Parallel evaluation
    disp=True,
)
```

### Phase 3: Visualization

1. **Swarm animation**: Show particles converging over iterations
2. **Final distribution**: Where did particles end up?
3. **Best position overlay**: Skylines at PSO-found position

### Phase 4: Comparison Experiments

Run PSO with different settings:
1. Swarm size: 20 vs 50 particles
2. Search radius: ±50m vs ±100m vs ±200m
3. Compare with Nelder-Mead and grid search results

## File Structure

```
pos-pso/
├── plan.md                    # This file
├── position_pso.py            # Main implementation
├── tmp/
│   ├── swarm_convergence.png  # Particles over iterations
│   ├── final_positions.png    # Final particle distribution
│   └── refined_skylines.jpg   # Best result overlay
```

## Key Functions to Implement

```python
def position_objective_pso(
    position: np.ndarray,  # [dx, dy] from GPS
    *args,                 # Unpacked: image_skyline, dem_loader, etc.
) -> float:
    """
    Objective function for PSO (same signature as pyswarm expects).
    Returns negative correlation (to minimize).
    """
    pass

def refine_position_pso(
    image_path: str,
    gps_lat: float,
    gps_lon: float,
    gps_alt: float,
    search_radius_m: float = 100.0,
    swarm_size: int = 30,
    max_iterations: int = 50,
) -> dict:
    """
    Refine camera position using Particle Swarm Optimization.

    Returns:
        dict with:
            - refined_position: (lat, lon, alt)
            - offset_from_gps: (dx, dy) in meters
            - final_correlation: float
            - iterations: int
            - swarm_history: list of particle positions per iteration
            - all_particles_final: final positions of all particles
    """
    pass

def visualize_swarm(swarm_history: list, best_position: tuple, output_path: str):
    """Create animation or plot of swarm convergence."""
    pass
```

## Comparison with Other Methods

| Aspect | Grid Search | Nelder-Mead | PSO |
|--------|-------------|-------------|-----|
| Function evaluations | O(n²) | O(50-100) | O(swarm × iters) |
| Global vs local | Global within grid | Local only | Global within bounds |
| Parallelizable | Yes | No | Yes |
| Handles local optima | N/A | Gets stuck | Escapes them |
| Best use | Exploration | Refinement | Robust search |

**Recommended workflow**:
1. Grid search (coarse) to visualize landscape
2. PSO for robust global search
3. Nelder-Mead for final polish (optional)

## Success Criteria

1. **Finds good solution**: Correlation ≥ grid search best
2. **Robust**: Multiple runs converge to similar solution
3. **Efficient**: Fewer evaluations than exhaustive grid for same quality
4. **Qualitative**: Refined position produces single peak matching image

## PSO Hyperparameter Tuning

Starting values (from literature):
- `swarmsize`: 30 (2D problem, moderate)
- `omega` (inertia): 0.7 (balance exploration/exploitation)
- `phip` (cognitive): 1.5 (personal best attraction)
- `phig` (social): 1.5 (global best attraction)
- `maxiter`: 50 (should converge well before this)
- `minstep`: 1.0 (1 meter position tolerance)

If PSO converges too slowly:
- Increase `omega` (more exploration)
- Decrease swarm size (faster iterations)

If PSO converges to wrong solution:
- Increase swarm size (better coverage)
- Widen search bounds
- Multiple restarts

## Potential Issues & Mitigations

1. **Slow function evaluation**: Each DEM render is expensive
   - Mitigation: Cache rendered skylines; use coarser DEM for initial iterations

2. **Premature convergence**: Swarm collapses before finding optimum
   - Mitigation: Increase inertia weight; use larger swarm

3. **Boundary effects**: Particles cluster at bounds
   - Mitigation: Ensure bounds are wide enough; check if true optimum is inside bounds

4. **Stochastic variation**: Different runs give different results
   - Mitigation: Set random seed for reproducibility; run multiple times and take best

## Dependencies

- `pyswarm` or `scipy.optimize.differential_evolution`
- Existing codebase: `skyline/dem/nagy_20.py`, `skyline/image/*.py`
- NumPy, Matplotlib
- pyproj for coordinate conversions

To install pyswarm:
```bash
uv add pyswarm
```

## Extensions to Consider

1. **3D search**: Include altitude (z) in optimization
2. **Joint pose**: Optimize [x, y, z, azimuth, pitch, roll] together
3. **Adaptive bounds**: Start wide, narrow as swarm converges
4. **Hybrid**: Use PSO to find basin, then Nelder-Mead to refine
