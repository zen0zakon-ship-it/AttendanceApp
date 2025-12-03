# app/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import date, time, datetime


# ---------- Пользователи ----------

class StudentRegister(BaseModel):
    full_name: str
    phone: str
    password: str
    group_id: int
    flow_code: str
    device_id: str


class LoginRequest(BaseModel):
    phone: str
    password: str
    device_id: Optional[str] = None


class UserOut(BaseModel):
    id: int
    full_name: str
    phone: str
    role: str
    group_id: Optional[int]

    class Config:
        from_attributes = True


# ---------- Checkin ----------

class CheckinRequest(BaseModel):
    flow_code: str
    device_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None


class CheckinResponse(BaseModel):
    ok: bool
    status: str
    message: str


class AttendanceRecord(BaseModel):
    student_id: int
    full_name: str
    checkin_time: Optional[time]
    status: str

    class Config:
        from_attributes = True
