from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, status, HTTPException

from database import Base, engine, SessionLocal
import models
import schemas


# -----------------------------
# DATABASE SETUP
# -----------------------------

Base.metadata.create_all(bind=engine)


# -----------------------------
# FASTAPI APPLICATION
# -----------------------------

app = FastAPI()


# -----------------------------
# DATABASE DEPENDENCY
# -----------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# -----------------------------
# HELPER: AUTO-RESTORE
# -----------------------------

def restore_shed_appliances(db):
    CAPACITY = 800

    # Get all currently running appliances
    running_appliances = (
        db.query(models.Appliance)
        .filter(models.Appliance.state == "RUNNING")
        .all()
    )

    current_load = sum(
        appliance.wattage
        for appliance in running_appliances
    )

    # Restore higher priority appliances first
    # Priority 1 is most important
    # If priority is same, restore lower ID first
    shed_appliances = (
        db.query(models.Appliance)
        .filter(models.Appliance.state == "SHED")
        .order_by(
            models.Appliance.priority.asc(),
            models.Appliance.id.asc()
        )
        .all()
    )

    restored_names = []

    for appliance in shed_appliances:

        # Restore only if it fits
        if current_load + appliance.wattage <= CAPACITY:

            appliance.state = "RUNNING"
            current_load += appliance.wattage

            restored_names.append(appliance.name)

    return restored_names


# -----------------------------
# HOME ENDPOINT
# -----------------------------

@app.get("/")
def home():
    return {
        "message": "Inverter Load Manager API is running"
    }


# -----------------------------
# CREATE APPLIANCE
# -----------------------------

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


# -----------------------------
# GET FULL SYSTEM STATE
# -----------------------------

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


# -----------------------------
# TURN APPLIANCE ON
# -----------------------------

@app.post("/appliances/{appliance_id}/on")
def turn_on_appliance(
    appliance_id: int,
    db: Session = Depends(get_db)
):
    CAPACITY = 800

    # Find requested appliance
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

    # Already running
    if target.state == "RUNNING":
        return {
            "message": f"{target.name} is already running",
            "shed_appliances": []
        }

    # Get currently running appliances
    running_appliances = (
        db.query(models.Appliance)
        .filter(models.Appliance.state == "RUNNING")
        .all()
    )

    current_load = sum(
        appliance.wattage
        for appliance in running_appliances
    )

    # Fits without shedding
    if current_load + target.wattage <= CAPACITY:

        target.state = "RUNNING"

        db.commit()

        return {
            "message": f"{target.name} turned on",
            "shed_appliances": []
        }

    # Only appliances with lower priority can be shed
    # Higher priority number = less important
    candidates = [
        appliance
        for appliance in running_appliances
        if appliance.priority > target.priority
    ]

    # Shed lowest priority first
    # Same priority -> larger wattage first
    candidates.sort(
        key=lambda appliance: (
            -appliance.priority,
            -appliance.wattage
        )
    )

    # Calculate BEFORE changing database
    load_after_shedding = current_load
    appliances_to_shed = []

    for appliance in candidates:

        load_after_shedding -= appliance.wattage
        appliances_to_shed.append(appliance)

        if load_after_shedding + target.wattage <= CAPACITY:
            break

    # Not enough capacity even after considering all
    # lower-priority appliances
    if load_after_shedding + target.wattage > CAPACITY:

        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot turn on {target.name}: "
                "not enough capacity after considering all "
                "lower-priority running appliances."
            )
        )

    # Apply changes only after confirming success
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


# -----------------------------
# TURN APPLIANCE OFF
# -----------------------------

@app.post("/appliances/{appliance_id}/off")
def turn_off_appliance(
    appliance_id: int,
    db: Session = Depends(get_db)
):
    # Find appliance
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

    # User explicitly turns it OFF.
    # If it was SHED, it will no longer be restored.
    target.state = "OFF"

    # Try restoring appliances waiting in SHED state
    restored_names = restore_shed_appliances(db)

    # Save everything together
    db.commit()

    return {
        "message": f"{target.name} turned off",
        "restored_appliances": restored_names
    }

@app.delete("/appliances/{appliance_id}")
def delete_appliance(
    appliance_id: int,
    db: Session = Depends(get_db)
):
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

    appliance_name = target.name

    # Delete the appliance
    db.delete(target)

    # Flush deletion so restore logic sees updated database state
    db.flush()

    # Capacity may now be available
    restored_names = restore_shed_appliances(db)

    db.commit()

    return {
        "message": f"{appliance_name} deleted",
        "restored_appliances": restored_names
    }