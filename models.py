from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey
from sqlalchemy.orm import relationship


class User(BaseModel):
    id: int
    username: str
    role: str


class UserInDb(User):
    password_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


class CreateAttendance(BaseModel):
    student_id: int
    class_section_id: int
    status: str


class AnnouncementCreate(BaseModel):
    subject: str
    details: str
    roles: List[str]
