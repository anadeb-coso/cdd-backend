from dataclasses import dataclass
from typing import Optional, List

@dataclass(frozen=True)
class FacilitatorCriteria:
    id__in: Optional[List[int]] = None
    develop_mode: Optional[bool] = None
    training_mode: Optional[bool] = None
    active: Optional[bool] = None
    projects__id: Optional[List[str]] = None
    no_sql_pass: Optional[str] = None
    no_sql_user: Optional[str] = None
    facilitator_type: Optional[str] = None
