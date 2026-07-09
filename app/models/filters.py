from typing import Optional
from pydantic import BaseModel

class SearchFilters(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    skills: Optional[str] = None
    company: Optional[str] = None
    keyword: Optional[str] = None
    visa: Optional[bool] = None
    posted_days: Optional[int] = None
    page: int = 1
    sort: Optional[str] = None
