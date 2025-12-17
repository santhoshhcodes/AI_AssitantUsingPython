from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from datetime import datetime
import pandas as pd
import os
import tempfile

from database.database import get_db, DATABASES

router = APIRouter()


@router.get("/sales/report/excel")
def download_sales_report():
    data = []

    try:
        for db_key in DATABASES.keys():
            db = next(get_db(db_key))

            rows = db.execute(text("""
                SELECT TOP 10
                    EmpNo,
                    FirstName,
                    EmployeeMobile,
                    Designation,
                    DeptName,
                    isActive
                FROM Employee_Mst
                ORDER BY FirstName
            """)).fetchall()

            for r in rows:
                data.append({
                    "Emp No": r.EmpNo,
                    "Employee Name": r.FirstName,
                    "Mobile": r.EmployeeMobile,
                    "Designation": r.Designation,
                    "Department": r.DeptName,
                    "Status": "Active" if r.isActive else "Inactive"
                })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not data:
        raise HTTPException(status_code=404, detail="No data found")

    df = pd.DataFrame(data)

    filename = f"employee_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(tempfile.gettempdir(), filename)

    df.to_excel(filepath, index=False, engine="openpyxl")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
