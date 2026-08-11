from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated


CanonicalField = Literal[
    "timestamp",
    "revenue",
    "event_id",
    "customer_id",
    "category",
    "region",
    "source",
    "product",
    "currency",
    "is_conversion",
]
DataType = Literal["STRING", "NUMBER", "BOOLEAN", "DATE_TIME", "CURRENCY"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreviewRequest(StrictModel):
    sheet_name: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
        ]
        | None
    ) = None


class FieldMapping(StrictModel):
    source_column: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    canonical_field: CanonicalField
    data_type: DataType


class ImportRequest(StrictModel):
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    sheet_name: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
        ]
        | None
    ) = None
    allow_partial: bool = False
    fields: list[FieldMapping] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def unique_mapping(self):
        canonical = [field.canonical_field for field in self.fields]
        source = [field.source_column for field in self.fields]
        if len(canonical) != len(set(canonical)):
            raise ValueError("Each canonical field may be mapped only once")
        if len(source) != len(set(source)):
            raise ValueError("Each source column may be mapped only once")
        return self


CANONICAL_SCHEMA = [
    {
        "field": "timestamp",
        "required": True,
        "allowed_types": ["DATE_TIME"],
        "description": "Event or order timestamp",
    },
    {
        "field": "revenue",
        "required": True,
        "allowed_types": ["NUMBER", "CURRENCY"],
        "description": "Revenue amount",
    },
    {
        "field": "event_id",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Unique event/order identifier",
    },
    {
        "field": "customer_id",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Customer identifier",
    },
    {
        "field": "category",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Product or event category",
    },
    {
        "field": "region",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Geographic region",
    },
    {
        "field": "source",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Acquisition or record source",
    },
    {
        "field": "product",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "Product name",
    },
    {
        "field": "currency",
        "required": False,
        "allowed_types": ["STRING"],
        "description": "ISO currency code",
    },
    {
        "field": "is_conversion",
        "required": False,
        "allowed_types": ["BOOLEAN"],
        "description": "Whether the record is a conversion",
    },
]
