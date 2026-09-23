from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SegmentRule(BaseModel):
    field: Literal["event_name", "source", "device", "region", "product", "revenue"]
    operator: Literal["eq", "neq", "in", "gte", "lte"]
    value: str | float | list[str]


class SegmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    match_type: Literal["ALL", "ANY"] = "ALL"
    rules: list[SegmentRule] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_rule_values(self):
        for rule in self.rules:
            if rule.operator == "in" and not isinstance(rule.value, list):
                raise ValueError("The in operator requires a list value")
            if rule.field == "revenue" and rule.operator not in {
                "eq",
                "neq",
                "gte",
                "lte",
            }:
                raise ValueError("Revenue only supports numeric comparison operators")
        return self
