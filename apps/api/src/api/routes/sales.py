"""
The sample sales database, for the frontend's SQL database page.

    GET /sales/tables                     tables, columns, row counts
    GET /sales/tables/{name}/rows         one page of rows: ?offset=0&limit=50&sort=column&order=asc|desc

No model calls, so no Gemini quota is used. Rows are read with checked SQL
over the same read-only connection as the SQL agent.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.rate_limit import client_key
from api.sales.catalog import MAX_PAGE_SIZE, InvalidSort, UnknownTable
from api.sales.database import QueryFailed
from api.schemas import SalesDatabaseInfo, TableRows
from api.services import Services, get_services

router = APIRouter(prefix="/sales", tags=["sales"])
logger = logging.getLogger(__name__)
ServicesDep = Annotated[Services, Depends(get_services)]


@router.get("/tables")
def list_tables(services: ServicesDep) -> SalesDatabaseInfo:
    try:
        return services.sales_catalog.describe()
    except QueryFailed:
        logger.exception("Describing the sales tables failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The database didn't answer. Try again in a moment."
        ) from None


@router.get("/tables/{name}/rows", response_model_exclude_none=True)
def table_rows(
    name: str,
    http: Request,
    services: ServicesDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    sort: str | None = None,
    order: Literal["asc", "desc"] = "asc",
) -> TableRows:
    # Cheap queries, but each one reaches the database, so browsing has a generous limit too.
    services.limits.browse.check(client_key(http))
    try:
        return services.sales_catalog.rows(name, offset=offset, limit=limit, sort=sort, order=order)
    except UnknownTable:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"There is no table called {name!r}.") from None
    except InvalidSort as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except QueryFailed:
        # A handled error keeps its CORS headers, so the page can show it and offer a retry.
        logger.exception("Reading rows of %s failed", name)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The database didn't answer. Try again in a moment."
        ) from None
