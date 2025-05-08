from pydantic import BaseModel
from typing import Literal, List, Optional


class CompareResult(BaseModel):
    status: Literal['new', 'existing', 'equal']
    embedding: Optional[List[float]] = None


test = CompareResult(status='new')
test1 = CompareResult(status=test.status)

print(test1)