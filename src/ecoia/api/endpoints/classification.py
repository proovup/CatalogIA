from fastapi import APIRouter, status

from ecoia.schemas.classification import ClassificationRequest, ClassificationResponse
from ecoia.services.classification_service import ClassificationService

router = APIRouter(prefix="/classification", tags=["classification"])


def get_classification_service() -> ClassificationService:
    return ClassificationService()


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
)
async def classify_product(request: ClassificationRequest):
    service = ClassificationService(provider=request.provider, model_name=request.model_name)
    return await service.classify(request)
