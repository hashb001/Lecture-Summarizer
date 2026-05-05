from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    subject: Optional[str] = Field(default=None, max_length=255)


class CourseCreate(CourseBase):
    pass


class CourseOut(CourseBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SummaryCreate(BaseModel):
    course_id: int
    session_id: Optional[str] = None
    source_filename: Optional[str] = None
    title: Optional[str] = None
    summary_text: Optional[str] = None
    slides_payload: Optional[Any] = None


class SummaryOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str]
    summary_text: str
    slides_payload: Optional[Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentOut(BaseModel):
    id: int
    course_id: int
    user_id: int
    title: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuizOut(BaseModel):
    id: int
    course_id: int
    user_id: int
    title: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
