from typing import Optional, List
from pydantic import BaseModel, Field

class JobSchema(BaseModel):
    id: str
    title: str
    company: str
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    skills: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    posted_date: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    job_url: str
    apply_url: Optional[str] = None
    source: str
    company_logo: Optional[str] = None
    applicants: Optional[int] = None
