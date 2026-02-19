from fastapi import APIRouter
from ecoia.api.endpoints.products import routes_crud, routes_extract, routes_ai

router = APIRouter(prefix="/products", tags=["products"])

router.include_router(routes_crud.router)
router.include_router(routes_extract.router)
router.include_router(routes_ai.router)
