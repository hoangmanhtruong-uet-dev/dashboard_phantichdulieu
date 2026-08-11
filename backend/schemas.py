from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonEmptyText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
DescriptionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SalesData(StrictModel):
    ds: NonEmptyText
    y: float = Field(ge=0)


class CustomerData(StrictModel):
    id: NonEmptyText
    frequency: int = Field(ge=0)
    monetary: float = Field(ge=0)


class ChatRequest(StrictModel):
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class AlertCreate(StrictModel):
    title: NonEmptyText
    description: DescriptionText
    severity: str = Field(default="medium", pattern="^(low|medium|high|success)$")


class ReportCreate(StrictModel):
    name: NonEmptyText
    report_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ] = "custom"


class DataSourceCreate(StrictModel):
    name: NonEmptyText
    source_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]


class ProfileUpdate(StrictModel):
    full_name: NonEmptyText
    job_title: NonEmptyText
    email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=254,
            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        ),
    ]
    phone: Optional[
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
    ] = ""
    workspace: Optional[NonEmptyText] = "Nexus Team"
