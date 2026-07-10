from typing import Optional
from pydantic import BaseModel, Field

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
    source: str = Field(..., description="The source to scrape (e.g., greenhouse, lever, linkedin)")
    company: Optional[str] = Field(None, description="The company slug or name")
    keyword: Optional[str] = Field(None, description="Search by keyword or job title")
    visa: Optional[bool] = None
    posted_days: Optional[int] = None
    page: int = 1
    sort: Optional[str] = None
