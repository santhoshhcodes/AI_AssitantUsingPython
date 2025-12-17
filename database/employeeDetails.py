# app/resources/Login/Login.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database.database import get_db, DATABASES

router = APIRouter()


class EmployeeRequest(BaseModel):
    EmployeeMobile: str


@router.post("/employeeDetails")
def Employee_Details(data: EmployeeRequest):

    mobile = data.EmployeeMobile

    for db_key in DATABASES.keys():

        db: Session = next(get_db(db_key))

        sql = "SELECT EmployeeMobile,CompCode,LocCode,EmpNo, FirstName, isActive, WeekOff, Designation, DeptName, BaseSalary FROM Employee_Mst WHERE EmployeeMobile = :mobile"

        result = db.execute(text(sql), {"mobile": mobile}).fetchone()

        if result:
            return {
                "status": True,
                "message": "Employee details successfully",
                "db_key": db_key,
                "data": dict(result._mapping)
            }

    raise HTTPException(status_code=404, detail="Mobile number not found in any database")
