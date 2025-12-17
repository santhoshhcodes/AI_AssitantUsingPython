from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database.database import get_db, DATABASES

router = APIRouter()


@router.get("/employees")
def get_all_employees():
    """
    Get all employees (lightweight list)
    Used for AI resolution, dropdowns, analytics
    """

    employees = []

    for db_key in DATABASES.keys():
        db: Session = next(get_db(db_key))

        sql = """
            SELECT TOP 20
                EmpNo,
                FirstName,
                EmployeeMobile,
                Designation,
                DeptName,
                isActive
            FROM Employee_Mst
            ORDER BY FirstName
        """

        results = db.execute(text(sql)).fetchall()

        for row in results:
            emp = dict(row._mapping)
            emp["db_key"] = db_key   # important for future lookups
            employees.append(emp)

    if not employees:
        raise HTTPException(status_code=404, detail="No employees found")

    return {
        "status": True,
        "count": len(employees),
        "data": employees
    }
