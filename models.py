from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from pydantic.networks import EmailStr, HttpUrl

class Event(BaseModel):
    eventName: Optional[str] = None
    organiser: Optional[str] = None
    proposed_by: Optional[str] = None
    status: Optional[str] = None
    proposal: Optional[str] = None
    marketingFile: Optional[str] = None
    formLink: Optional[str] = None
    meetLink: Optional[str] = None
    contributedDate: Optional[str] = None
    eventDate: Optional[str] = None
    venue: Optional[str] = None
    time: Optional[str] = None
    suggestion: Optional[str] = None
    insta: Optional[str] = None
    linkedin: Optional[str] = None
    whatsapp: Optional[str] = None
    targetYear: Optional[List[str]] = [] 
    expectedParticipants: Optional[str] = None
    progressIndex: Optional[int] = 0
    banner: Optional[str] = None
    posterWhatsapp: Optional[str] = None
    posterInsta: Optional[str] = None
    preInstagram: Optional[str] = None
    preLinkedin: Optional[str] = None
    preYoutube: Optional[str] = None
    postInstagram: Optional[str] = None
    postLinkedin: Optional[str] = None
    postYoutube: Optional[str] = None
    submitted: Optional[bool] = False


class QueryModel(BaseModel):
    name: str
    category: str
    message: str
    created_at: Optional[datetime] = None

class LoginRequest(BaseModel):
    email: str
    password: str