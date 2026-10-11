from typing import Optional
from pydantic import BaseModel

class Trajectory(BaseModel):
    timestamp: str = None
    inventory: float = None
    demand: float = None
    action: str = None
    
class PlaceCell(BaseModel):
    state: str = None
    inventory: float = None
    amount: float = None

class Statistics(BaseModel):
    count: int = None
    mean: float = None
    std: float = None
    slope: float = None
    sum: float = None
    
class Amount(BaseModel):
    level: float = None
    statistics: Statistics = None

class Inventory(BaseModel):
    level: float = None
    available: int = None
    sold: int = None
    coverage_lead_time: float = None
    statistics: Statistics = None

class Price(BaseModel):
    currency: str = None
    amount: float = None

class Product(BaseModel):
    sku: str = None
    name: str = None
    lead_time: int = None
    price: Price = None

class ProductState(BaseModel):
    inventory_level: float = None
    amount_level: float = None

class Decision(BaseModel):
    grid_metadata: dict = None

class AgentGoal(BaseModel):
    goal: str = None
    sku: str = None
    objective: str = None
    action: str = None
    parameters: dict = None