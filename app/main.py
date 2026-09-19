from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import auth, documents, groups, questions

app = FastAPI(
    title="DocuQuest — Document Intelligence & Question Extraction Service",
    description=(
        "Accepts PDF/image question-bank documents, processes them asynchronously "
        "(OCR + rule-based extraction), and exposes structured questions and "
        "answer-key associations with confidence scoring and review flags."
    ),
    version="1.0.0",
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(groups.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
