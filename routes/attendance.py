from datetime import date
from operator import and_
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import require_role
from db import get_db
from models import Attendance, CreateAttendance

router = APIRouter()


@router.post("/attendance/bulk", dependencies=[Depends(require_role(["teacher"]))])
def mark_bulk_attendance(datas: List[CreateAttendance], db: Session = Depends(get_db)):
    attendance = [
        Attendance(
            student_id=data.student_id,
            class_section_id=data.class_section_id,
            date=date.today(),
            status=data.status,
        )
        for data in datas
    ]
    try:
        db.add_all(attendance)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attendance already marked for {date.today()}",
        )
    return "done"


@router.post("/attendance", dependencies=[Depends(require_role(["teacher"]))])
def mark_attendance(data: CreateAttendance, db: Session = Depends(get_db)):
    try:
        attendance = Attendance(
            student_id=data.student_id,
            class_section_id=data.class_section_id,
            date=date.today(),
            status=data.status,
        )

        db.add(attendance)
        db.commit()
        db.refresh(attendance)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attendance already marked for {date.today()}",
        )

    return attendance.student_id


@router.get("/attendance/today", dependencies=[Depends(require_role(["teacher"]))])
def get_attendance(class_section_id: int, db: Session = Depends(get_db)):
    data = (
        db.query(Attendance)
        .where(
            and_(
                Attendance.date == date.today(),
                Attendance.class_section_id == class_section_id,
            )
        )
        .all()
    )

    return [
        {
            "student_id": d.student_id,
            "class_section_id": d.class_section_id,
            "status": d.status,
        }
        for d in data
    ]
