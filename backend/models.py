from sqlalchemy import Column, Integer, String

from database import Base


class Appliance(Base):
    __tablename__ = "appliances"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    wattage = Column(Integer, nullable=False)

    priority = Column(Integer, nullable=False)

    state = Column(
        String,
        nullable=False,
        default="OFF"
    )