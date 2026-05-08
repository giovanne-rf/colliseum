from __future__ import annotations

from enum import StrEnum


class Belt(StrEnum):
    white = "white"
    gray = "gray"
    gray_white = "gray_white"
    gray_black = "gray_black"
    yellow = "yellow"
    yellow_white = "yellow_white"
    yellow_black = "yellow_black"
    orange = "orange"
    orange_white = "orange_white"
    orange_black = "orange_black"
    green = "green"
    green_white = "green_white"
    green_black = "green_black"
    blue = "blue"
    purple = "purple"
    brown = "brown"
    black = "black"
    red_black = "red_black"
    red_white = "red_white"
    red = "red"


class Sex(StrEnum):
    male = "male"
    female = "female"
