from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, status, HTTPException
from database import Base, engine, SessionLocal
import models
import schemas


# Create database tables
Base.metadata.create_all(bind=engine)


# Create FastAPI application
app = FastAPI()


# Database dependency
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Inverter Load Manager API is running"
    }


# Create appliance
@app.post("/appliances", status_code=status.HTTP_201_CREATED)
def create_appliance(
    appliance: schemas.ApplianceCreate,
    db: Session = Depends(get_db)
):
    new_appliance = models.Appliance(
        name=appliance.name,
        wattage=appliance.wattage,
        priority=appliance.priority,
        state="OFF"
    )

    db.add(new_appliance)
    db.commit()
    db.refresh(new_appliance)

    return {
        "id": new_appliance.id,
        "name": new_appliance.name,
        "wattage": new_appliance.wattage,
        "priority": new_appliance.priority,
        "state": new_appliance.state
    }


# Get complete inverter system state
@app.get("/appliances")
def get_appliances(
    db: Session = Depends(get_db)
):
    appliances = db.query(models.Appliance).all()

    current_load = sum(
        appliance.wattage
        for appliance in appliances
        if appliance.state == "RUNNING"
    )

    capacity = 800
    remaining_capacity = capacity - current_load

    appliance_list = []

    for appliance in appliances:
        appliance_list.append({
            "id": appliance.id,
            "name": appliance.name,
            "wattage": appliance.wattage,
            "priority": appliance.priority,
            "state": appliance.state
        })

    return {
        "capacity": capacity,
        "current_load": current_load,
        "remaining_capacity": remaining_capacity,
        "appliances": appliance_list
    }

@app.post("/appliances/{appliance_id}/on")
def turn_on_appliance(
    appliance_id: int,
    db: Session = Depends(get_db)
):
    CAPACITY = 800

    # Find the appliance
    target = (
        db.query(models.Appliance)
        .filter(models.Appliance.id == appliance_id)
        .first()
    )

    if not target:
        raise HTTPException(
            status_code=404,
            detail="Appliance not found"
        )

    # If already running, no change needed
    if target.state == "RUNNING":
        return {
            "message": f"{target.name} is already running",
            "shed_appliances": []
        }

    # Calculate current running load
    running_appliances = (
        db.query(models.Appliance)
        .filter(models.Appliance.state == "RUNNING")
        .all()
    )

    current_load = sum(
        appliance.wattage
        for appliance in running_appliances
    )

    # If it fits directly, turn it on
    if current_load + target.wattage <= CAPACITY:
        target.state = "RUNNING"
        db.commit()

        return {
            "message": f"{target.name} turned on",
            "shed_appliances": []
        }

    # Find appliances with LOWER priority
    # Higher number = lower importance
    candidates = [
        appliance
        for appliance in running_appliances
        if appliance.priority > target.priority
    ]

    # Shed lowest priority first
    # For same priority, shed larger wattage first
    candidates.sort(
        key=lambda appliance: (
            -appliance.priority,
            -appliance.wattage
        )
    )

    # IMPORTANT:
    # First decide whether enough capacity can be freed.
    # Do not change the database yet.
    load_after_shedding = current_load
    appliances_to_shed = []

    for appliance in candidates:

        load_after_shedding -= appliance.wattage
        appliances_to_shed.append(appliance)

        if load_after_shedding + target.wattage <= CAPACITY:
            break

    # If even shedding everything is not enough,
    # reject without changing anything.
    if load_after_shedding + target.wattage > CAPACITY:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot turn on {target.name}: "
                "not enough capacity after considering all "
                "lower-priority running appliances."
            )
        )

    # Now apply all changes together
    shed_names = []

    for appliance in appliances_to_shed:
        appliance.state = "SHED"
        shed_names.append(appliance.name)

    target.state = "RUNNING"

    db.commit()

    return {
        "message": (
            f"{target.name} turned on. "
            f"Shed: {', '.join(shed_names)}"
        ),
        "shed_appliances": shed_names
    }