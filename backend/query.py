from dataclasses import dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class PageSpec:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def meta(self, total: int) -> dict[str, int]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": total,
            "total_pages": ceil(total / self.page_size) if total else 0,
        }


def query_meta(
    page: PageSpec,
    total: int,
    *,
    search: str = "",
    filters: dict[str, Any] | None = None,
    sort_by: str,
    sort_order: str,
) -> dict:
    return {
        "pagination": page.meta(total),
        "query": {
            "search": search,
            "filters": filters or {},
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    }
