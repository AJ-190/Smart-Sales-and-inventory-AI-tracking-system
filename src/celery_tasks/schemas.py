from pydantic import BaseModel
from fastapi_mail import NameEmail
from typing import List

class Emailschema(BaseModel):
    email = List[NameEmail]