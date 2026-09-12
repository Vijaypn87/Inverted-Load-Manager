from fastapi import FastAPI

from database import Base, engine

import models


Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def home():
    return {
        "message": "Inverter Load Manager API is running"
    }