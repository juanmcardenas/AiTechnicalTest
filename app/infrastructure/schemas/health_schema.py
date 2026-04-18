from pydantic import BaseModel


class DependencyStatus(BaseModel):
    database: str
    deepseek: str
    langfuse: str


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: DependencyStatus
