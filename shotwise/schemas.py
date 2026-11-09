from typing import Literal

from pydantic import BaseModel, Field


class Line(BaseModel):
    speaker: str                      # a character name from the bible
    text: str
    emotion: str = "neutral"          # passed to the TTS provider


class Shot(BaseModel):
    id: str                           # "s03_07": scene 3, shot 7
    duration_s: float = Field(ge=2, le=12)
    shot_type: Literal["establishing", "wide", "medium", "closeup_dialogue", "insert"]
    characters: list[str] = []
    location: str
    camera: str                       # "slow push-in", "static", "pan left"
    action: str                       # what the viewer sees happen
    lines: list[Line] = []
    needs_video: bool = True          # False: approved keyframe + camera move in the edit
    lane: Literal["free", "premium"] = "free"   # premium = make by hand in Flow / Nano Banana Pro


class Scene(BaseModel):
    id: str
    title: str
    location: str
    time_of_day: str
    mood: str                         # drives the music prompt
    shots: list[Shot]


class Breakdown(BaseModel):
    episode: str
    logline: str
    scenes: list[Scene]


BREAKDOWN_SCHEMA = Breakdown.model_json_schema()
