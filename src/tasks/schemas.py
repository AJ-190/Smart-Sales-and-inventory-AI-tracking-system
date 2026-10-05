from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CronJobOut(BaseModel):
    id: str
    name: str
    label: str
    description: str
    schedule: str
    trigger: str
    timezone: str
    running: bool
    pending: bool
    next_run: Optional[datetime] = None


class CronTriggerResult(BaseModel):
    id: str
    triggered: bool
    detail: str
