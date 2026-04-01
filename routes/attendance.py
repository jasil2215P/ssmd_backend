from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from auth import require_role
from db import get_db
from models import CreateAttendance

router = APIRouter()


@router.post("/attendance/bulk", dependencies=[Depends(require_role(["teacher"]))])
def mark_bulk_attendance(datas: List[CreateAttendance], db=Depends(get_db)):
    query = text("""
        INSERT INTO attendance
        (student_id, class_section_id, date, status)
        VALUES
        (:student_id, :class_section_id, CURRENT_DATE, :status)
        RETURNING student_id
    """)

    arguments = [data.model_dump() for data in datas]
    try:
        db.execute(query, arguments)

        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attendance already marked for {date.today()}",
        )
    return "done"


@router.post("/attendance", dependencies=[Depends(require_role(["teacher"]))])
def mark_attendance(data: CreateAttendance, db=Depends(get_db)):
    query = text("""
        INSERT INTO attendance
        (student_id, class_section_id, date, status)
        VALUES
        (:student_id, :class_section_id, CURRENT_DATE, :status)
        RETURNING student_id
    """)
    try:
        id = db.execute(
            query,
            {
                "student_id": data.student_id,
                "class_section_id": data.class_section_id,
                "status": data.status,
            },
        ).fetchone()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attendance already marked for {date.today()}",
        )

    return id._mapping


@router.get("/attendance/today", dependencies=[Depends(require_role(["teacher"]))])
def get_attendance(class_section_id, db=Depends(get_db)):
    query = text("""
        SELECT student_id, class_section_id, status FROM attendance WHERE
        date = :date and class_section_id = :class_section_id
    """)

    results = db.execute(
        query, {"date": date.today(), "class_section_id": class_section_id}
    ).fetchall()

    return [dict(row._mapping) for row in results]
