# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

# SQL Server (LOCAL MACHINE)
SERVER = "LAPTOP-UMDMOS9I"
USERNAME = "sa"
PASSWORD = "sanvi9691"

# List of databases
DATABASES = {
    "db1": "ESM_Spay"
    # "db2": "ESM_DYEING_ERP",
    # "db3": "ESM_DYEING_ACCOUNTS",
    # "db4": "ESM_Spay_Knitting",
    # "db5": "ESM_KNITTING_ERP",
    # "db6": "ESM_KNITTING_ACCOUNTS",
    # "db7": "ESM_Spay_yarn",
    # "db8": "ESM_SPINNING_ERP",
    # "db9": "ESM_SPINNING_ACCOUNTS",
}

_engines = {}
_sessions = {}

def _create_engine(dbname: str):
    # Use pymssql instead of pyodbc
    db_url = f"mssql+pymssql://{USERNAME}:{PASSWORD}@{SERVER}/{dbname}"
    return create_engine(db_url, echo=False)

def get_db(db_key: str):
    if db_key not in DATABASES:
        raise HTTPException(status_code=400, detail=f"Invalid DB key: {db_key}")

    if db_key not in _engines:
        _engines[db_key] = _create_engine(DATABASES[db_key])
        _sessions[db_key] = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_engines[db_key]
        )

    db = _sessions[db_key]()
    try:
        yield db
    finally:
        db.close()
