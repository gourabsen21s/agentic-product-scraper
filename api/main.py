# api/main.py
from fastapi import FastAPI
from .deps import init_services
from .routes import session_routes, artifact_routes
from .routes import perception_routes
from .routes import plan_execute, plan_execute_loop

app = FastAPI(title="Browser Runner API")

@app.on_event("startup")
async def startup():
    await init_services(app)

# include routers
# app.include_router(health_routes.router, prefix="/api")
app.include_router(session_routes.router, prefix="/api")
app.include_router(artifact_routes.router, prefix="/api")
app.include_router(perception_routes.router, prefix="/api")
app.include_router(plan_execute.router, prefix="/api")
app.include_router(plan_execute_loop.router, prefix="/api")

