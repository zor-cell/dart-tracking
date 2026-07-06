from fastapi import APIRouter

router = APIRouter(tags=["System"])

@router.get("/")
async def health_check():
    """
    Simple health check endpoint
    """
    return {
        "status": "online",
        "message": "Dart tracking is healthy"
    }