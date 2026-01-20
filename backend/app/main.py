from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.api import api_router
from app.api.errors import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.services.processing_queue import get_processing_queue, cleanup_processing_queue
from app.services.service_coordinator import get_service_coordinator
from app.services.background_tasks import background_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Removed init_db() - we don't want to create standalone boo.db
    # User databases are initialized when users register/login
    # Shared auth database (user_registry.db) persists from registration
    
    # Initialize processing queue
    processing_queue = await get_processing_queue()
    
    # Initialize services (STT, WebSocket, Hotkey)
    service_coordinator = await get_service_coordinator()
    await service_coordinator.initialize()
    
    # Background memory processing now starts per-user after login
    
    yield
    
    # Shutdown
    await background_manager.stop()
    await cleanup_processing_queue()


app = FastAPI(
    title="Boo Journal API",
    description="Local-first journaling application with AI integration",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Authentication middleware removed - switching handled at login time

# Add exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "message": "Boo Journal API",
        "version": settings.VERSION,
        "status": "operational",
        "docs_url": "/docs"
    }