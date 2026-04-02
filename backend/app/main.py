from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import matches, players, stats


app = FastAPI(title="PNBallie")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(matches.router)
app.include_router(stats.router)
