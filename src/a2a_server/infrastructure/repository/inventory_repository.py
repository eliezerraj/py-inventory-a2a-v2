
import logging
import json

from src.a2a_server.domain.repository.contract import InventoryRepositoryContract

from pathlib import Path

from opentelemetry import trace

#---------------------------------
# Configure logging and tracer
#---------------------------------
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class InventoryRepository(InventoryRepositoryContract):
    
    def __init__(self):
        pass

    # Create a connection to the JSON file (simulated as a database connection)
    def _connect(self):
        """Create a database connection"""
        return None
        
    # Retrieve the place cell memory from the JSON file
    def get_place_cell(self):
        """Retrieve the place cell memory."""
        logger.info("Retrieving place cell memory")
        
        with tracer.start_as_current_span("repository.get_place_cell"):
            try:
                base_path = Path(__file__).parent.parent.parent.parent
                memory_path = base_path / "a2a_server/infrastructure/repository/dataset/place_cell.json"
                
                with open(memory_path, "r") as f:
                    self.memory = json.load(f)

                place_cell = {
                                item["state"]: (
                                item["inventory"],
                                item["amount"]
                                )
                                for item in self.memory["place_cell"]
                }
                
                logger.info("Successfully retrieved place cell memory: %s", place_cell)
                
            except Exception as e:
                logger.error("Error retrieving place cell memory: %s", e)
                raise RuntimeError(f"Error retrieving place cell memory") from e
            
            return place_cell

    def get_trajectory(self):
        """Retrieve the trajectory memory."""
        logger.info("Retrieving trajectory memory")
        
        with tracer.start_as_current_span("repository.get_trajectory"):
            try:
                base_path = Path(__file__).parent.parent.parent.parent
                memory_path = base_path / "a2a_server/infrastructure/repository/dataset/trajectory.json"
                
                with open(memory_path, "r") as f:
                    self.memory = json.load(f)

                trajectory = [
                                (
                                item["timestamp"],
                                item["inventory"],
                                item["demand"],
                                item["action"]
                                )
                                for item in self.memory["trajectory"]
                ]
                
                logger.info("Successfully retrieved trajectory memory %s", trajectory)
                
            except Exception as e:
                logger.error("Error retrieving trajectory memory: %s", e)
                raise RuntimeError(f"Error retrieving trajectory memory") from e
            
            return trajectory