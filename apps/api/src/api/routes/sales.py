"""GET /sales/tables: what the sample sales database contains, for the frontend's SQL database page."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.schemas import SalesDatabaseInfo
from api.services import Services, get_services

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/tables")
def list_tables(services: Annotated[Services, Depends(get_services)]) -> SalesDatabaseInfo:
    # No model calls and cached after the first request, so no rate limit is needed.
    return services.sales_catalog.describe()
