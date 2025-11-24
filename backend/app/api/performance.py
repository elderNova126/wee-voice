"""
Performance Monitoring API
Provides endpoints for monitoring application performance
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.core.security import get_current_active_user
from app.models import User
from app.core.performance import get_performance_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_performance_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current performance statistics
    (Admin only in production)
    """
    # In production, restrict to superusers
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    stats = await get_performance_stats()
    return stats


@router.get("/health")
async def health_check():
    """
    Detailed health check with performance metrics
    """
    try:
        # Check database connection
        from app.models.database import SessionLocal
        db = SessionLocal()
        try:
            # Simple query to test database
            db.execute("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = f"unhealthy: {str(e)}"
        finally:
            db.close()
        
        # Get performance stats
        perf_stats = await get_performance_stats()
        
        # Determine overall status
        overall_status = "healthy" if db_status == "healthy" else "degraded"
        
        return {
            "status": overall_status,
            "database": db_status,
            "performance": {
                "cache_entries": perf_stats.get("cache_size", 0),
                "active_connections": {
                    "openai": perf_stats.get("openai_connections", 0),
                    "gemini": perf_stats.get("gemini_connections", 0),
                    "smtp": perf_stats.get("smtp_connections", 0)
                }
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

