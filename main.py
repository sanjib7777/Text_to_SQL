from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from settings import CORS_ORIGINS


app = FastAPI(
    title="AI SQL Generation API",
    description=(
        "Natural Language to Oracle SQL "
        "Generation and Execution API"
    ),
    version="1.0.0",
    swagger_ui_parameters={"syntaxHighlight": False}
)

# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Register routes
# ---------------------------------------------------------

app.include_router(
    router,
    prefix="/api"
)


@app.get("/")
def root():

    return {
        "message": "AI SQL Generation API is running."
    }