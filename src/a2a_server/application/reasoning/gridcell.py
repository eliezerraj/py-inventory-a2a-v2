import numpy as np
import logging

logger = logging.getLogger(__name__)

class GridCellModule:

    # Load and initialize a Grid Cell Module with specified scale, anchor, and random seed.
    def __init__(self, scale, anchor_coord=None, rng_seed=42, verbose=False):
        self.scale = scale
        self.anchor_coord = anchor_coord
        self.verbose = verbose
        self.rng = np.random.default_rng(rng_seed)
        self.orientation = self.rng.uniform(0, 2 * np.pi)
        self.params = {}
        
        # 1. Define the 3 wave vectors for a hexagonal grid (120-degree offsets)
        angles = np.array([
            self.orientation, 
            self.orientation + 2 * np.pi / 3, 
            self.orientation + 4 * np.pi / 3
        ])
        self.k_x = np.cos(angles)
        self.k_y = np.sin(angles)
        
        # 2. PHASE ANCHORING LOGIC
        if self.anchor_coord is not None:
            # We calculate a unique phase for each of the 3 waves to force them 
            # to all peak simultaneously at the anchor_coord.
            # Formula: phase = -(k · x) / scale
            self.phases = -(self.k_x * anchor_coord[0] + self.k_y * anchor_coord[1]) / self.scale
        else:
            self.phases = self.rng.uniform(0, 2 * np.pi, 3)
        
        self.params = {
                "k_x": self.k_x,        # Pre-calculated
                "k_y": self.k_y,        # Pre-calculated
                "phases": self.phases,   # Pre-calculated
                "scale": self.scale,
                "orientation": self.orientation
        }
        
        logger.info("GridCellModule initialized SUCCESSFULLY")
           
    # Compute the grid cell activation for a given 2D grid of positions (X, Y)
    def get_grid_activation(self, X, Y):
        # We use the pre-calculated k_x, k_y and phases
        # Proj becomes a (3, res, res) array
        proj = (self.k_x[:, None, None] * X + self.k_y[:, None, None] * Y) / self.scale + self.phases[:, None, None]
        
        # Sum the three cosines
        activation = np.sum(np.cos(proj), axis=0)
        # Normalize to [0, 1]
        return (activation + 1.5) / 4.5

    # Compute the grid cell activation for a single 2D position (pos)
    def get_single_activation(self, pos):
        # Compute the grid cell activation for a single 2D position (pos)
        proj = (self.k_x * pos[0] + self.k_y * pos[1]) / self.scale + self.phases
        activation = np.sum(np.cos(proj))
        if self.verbose:
            print(f"Calculating activation for position {pos} at scale '{self.scale}'")
            print(f"proj: {proj}")
            print(f"activation: {activation}")
        return (activation + 1.5) / 4.5