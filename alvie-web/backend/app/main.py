from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from . import models, schemas
from .database import Base, SessionDep, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine) # create DB tables if they don't exist
    yield


app = FastAPI(title="Alvie Parsed Output API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # allow access from remote clients. In production, use a DNS name or stable IP address
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


def _get_or_404(db: SessionDep, output_id: int) -> models.ParsedOutputRecord:
    record = db.get(models.ParsedOutputRecord, output_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsed output {output_id} not found.",
        )
    return record


@app.get("/api/outputs", response_model=list[schemas.ParsedOutputSummary])
def list_outputs(db: SessionDep) -> list[models.ParsedOutputRecord]:
    return (
        db.query(models.ParsedOutputRecord)
        .order_by(models.ParsedOutputRecord.created_at.desc())
        .all()
    )


@app.get("/api/outputs/{output_id}", response_model=schemas.ParsedOutputRead)
def get_output(output_id: int, db: SessionDep) -> models.ParsedOutputRecord:
    return _get_or_404(db, output_id)


@app.post(
    "/api/outputs",
    response_model=schemas.ParsedOutputRead,
    status_code=status.HTTP_201_CREATED,
)
def create_output(
    payload: schemas.ParsedOutputCreate, db: SessionDep
) -> models.ParsedOutputRecord:
    record = models.ParsedOutputRecord(
        filename=payload.filename,
        executable=payload.data.executable,
        start=payload.data.start,
        end=payload.data.end,
        data=payload.data.model_dump(mode="json", exclude_none=True), # exclude_none ensures that optional fields with None values are not stored in the database
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.patch("/api/outputs/{output_id}", response_model=schemas.ParsedOutputRead)
def update_output(
    output_id: int, payload: schemas.ParsedOutputUpdate, db: SessionDep
) -> models.ParsedOutputRecord:
    record = _get_or_404(db, output_id)
    record.filename = payload.filename
    db.commit()
    db.refresh(record)
    return record


@app.delete("/api/outputs/{output_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_output(output_id: int, db: SessionDep) -> None:
    record = _get_or_404(db, output_id)
    db.delete(record)
    db.commit()


@app.delete("/api/outputs", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_outputs(db: SessionDep) -> None:
    db.query(models.ParsedOutputRecord).delete()
    db.commit()
