from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import require_role
from db import get_db
from models import (
    Attendance,
    AttendanceCreateResponse,
    AttendanceRecordResponse,
    CreateAttendance,
    OperationStatusResponse,
)

router = APIRouter(tags=["attendance"])


@router.post(
    "/attendance/records/bulk",
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    summary="Create attendance records in bulk",
)
@router.post(
    "/attendance/bulk",
    include_in_schema=False,
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher"]))],
)
def create_bulk_attendance_records(
    datas: List[CreateAttendance], db: Session = Depends(get_db)
):
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
    return OperationStatusResponse(status="done")


@router.put(
    "/attendance/records/bulk",
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    summary="Update attendance records in bulk",
)
@router.put(
    "/attendance/bulk",
    include_in_schema=False,
    response_model=OperationStatusResponse,
    dependencies=[Depends(require_role(["teacher"]))],
)
def update_bulk_attendance_records(
    datas: List[CreateAttendance], db: Session = Depends(get_db)
):
    updated_attendance = 0

    for data in datas:
        updated_attendance += (
            db.query(Attendance)
            .where(
                and_(
                    Attendance.student_id == data.student_id,
                    Attendance.class_section_id == data.class_section_id,
                    Attendance.date == date.today(),
                )
            )
            .update({Attendance.status: data.status}, synchronize_session=False)
        )

    if updated_attendance != len(datas):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance not found for {date.today()}",
        )

    db.commit()
    return OperationStatusResponse(status="done")


@router.post(
    "/attendance/records",
    response_model=AttendanceCreateResponse,
    dependencies=[Depends(require_role(["teacher"]))],
    summary="Create a single attendance record",
)
@router.post(
    "/attendance",
    include_in_schema=False,
    response_model=AttendanceCreateResponse,
    dependencies=[Depends(require_role(["teacher"]))],
)
def create_attendance_record(data: CreateAttendance, db: Session = Depends(get_db)):
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

    return AttendanceCreateResponse(student_id=attendance.student_id)


@router.get(
    "/attendance/records/today",
    response_model=list[AttendanceRecordResponse],
    dependencies=[Depends(require_role(["teacher"]))],
    summary="List today's attendance records for a class section",
)
@router.get(
    "/attendance/today",
    include_in_schema=False,
    response_model=list[AttendanceRecordResponse],
    dependencies=[Depends(require_role(["teacher"]))],
)
def list_today_attendance_records(
    class_section_id: int, db: Session = Depends(get_db)
):
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
        AttendanceRecordResponse(
            student_id=d.student_id,
            class_section_id=d.class_section_id,
            status=d.status,
        )
        for d in data
    ]
