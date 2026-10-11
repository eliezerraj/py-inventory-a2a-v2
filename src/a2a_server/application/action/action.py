import logging
import json
import numpy as np

from pathlib import Path
from opentelemetry import trace

from src.a2a_server.infrastructure.repository.inventory_repository import InventoryRepository

#---------------------------------
# Configure logging and tracer
#---------------------------------
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class Action:
    
    def __init__(self):  
        inventory_repository = InventoryRepository()
        self.trajectory = inventory_repository.get_trajectory()
        self.transitions = self.build_transitions(self.trajectory)
                
        print("---------- start load transitions (Memory)----------------")
        print(self.transitions)
        print("----------end load transitions (Memory)----------------")
        
        logger.info("Action initialized SUCCESSFULLY")

    def build_transitions(self, trajectory):
        transitions = []

        for i in range(len(trajectory) - 1):

            current = trajectory[i]
            next_ = trajectory[i + 1]

            transitions.append({
                "from_time": current[0],
                "to_time": next_[0],

                "state": np.array(
                    [current[1], current[2]],
                    dtype=np.float32
                ),

                "action": current[3],

                "next_state": np.array(
                    [next_[1], next_[2]],
                    dtype=np.float32
                )
            })

        return transitions
    
    def distance_to_segment(self, point, start, end):
        logger.info(f"Calculating distance from point {point} to segment [{start}, {end}]")
        
        segment = end - start

        segment_length_squared = np.dot(segment, segment)

        # Degenerate segment
        if segment_length_squared == 0:
            return np.linalg.norm(point - start)

        # Position of the projection on the segment
        t = np.dot(point - start, segment) / segment_length_squared

        # Keep projection between start and end
        t = np.clip(t, 0.0, 1.0)

        projection = start + t * segment

        distance = np.linalg.norm(point - projection)

        return distance
    
    def predict_next_state( self, current_state, action=None, max_distance=0.05 ):
        """
        Predict the next state based on the current state and action.

        Args:
            current_state (np.array): The current state of the system.
            action (optional): The action to consider for the prediction.
            max_distance (float): The maximum allowable distance for a valid transition.

        Returns:
            tuple: The best transition and its distance, or None if no valid transition is found.
        """
        
        candidates = self.transitions

        if action is not None:
            candidates = [
                t for t in self.transitions
                if t["action"] == action
            ]

        best_transition = None
        best_distance = float("inf")

        for transition in candidates:
            distance = self.distance_to_segment(
                current_state,
                transition["state"],
                transition["next_state"]
            )
            if distance < best_distance:
                best_distance = distance
                best_transition = transition

        if best_transition is None:
            logger.warning("No suitable transition found.")
            return best_transition, best_distance

        if best_distance > max_distance:
            logger.warning(f"No valid transition within the allowable distance. Best distance {best_distance} exceeds max distance {max_distance}.")
            return best_transition, best_distance
 
        return best_transition, best_distance
    
    def take_action(self, current_state):
        logger.info(f"Taking action with current state: {current_state}")

        transition, distance = self.predict_next_state(current_state)
        return {
            "transition": transition["action"],
            "next_state": transition["next_state"].tolist(),  # Convert numpy array to list
            "transition_time": f"{transition['from_time']} → {transition['to_time']}",
            "distance": float(distance)  # Convert numpy scalar to Python float
        } 
