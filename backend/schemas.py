from pydantic import BaseModel, Field


class ApplianceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wattage: int = Field(gt=0)
    priority: int = Field(ge=1)