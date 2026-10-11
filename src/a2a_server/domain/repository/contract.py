from abc import ABC, abstractmethod

from typing import List, Optional

from src.a2a_server.domain.dto.model import Trajectory, PlaceCell

class InventoryRepositoryContract(ABC):

    @abstractmethod
    def get_place_cell(self) -> List[PlaceCell]:
        """Retrieve the place cell."""
        pass

    @abstractmethod
    def get_trajectory(self) -> List[Trajectory]:
        """Retrieve all trajectory memories."""
        pass
