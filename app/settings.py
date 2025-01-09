__all__ = [
    "DATE_FORMAT",
    # "formatwarning",
    "METADATA",
    "MPL_RUNTIME_CONFIG",
    "S3_URL_LIFESPAN",
    "SCALE_MIN",
    "SCALE_MAX",
    "STATUS_OK",
    "STATUS_NOK"
]

# standard library
from collections import namedtuple
from typing import Any

# 3rd party libraries
from fastapi import status


# date format used throughout the project
DATE_FORMAT: str = "%d.%m.%Y"


# def formatwarning(message, category, *_) -> str:
#     """
#     Conservative custom warning formatter to replace standard
#     https://docs.python.org/3.13/library/warnings.html#warnings.formatwarning
#     """
#     return f"{category.__name__}: {message}\n"


# field metadata, e.g. thresholds (min and max valid values)
Metadata = namedtuple("Metadata", ["ge", "le"])

METADATA: dict[str, Metadata] = {
    "periods": Metadata(ge=1,      le=60),
    "amount":  Metadata(ge=10_000, le=3_000_000),
    "rate":    Metadata(ge=1,      le=8)
}

# matplotlib runtime configuration
MPL_RUNTIME_CONFIG: dict[str, Any] = {
    "axes.titlepad": 15,
    "figure.dpi": 120
}

# lifespan of a link to a deposit balance progress chart, seconds
S3_URL_LIFESPAN: int = 180

# thresholds to dynamically clamp amount handler's scale factor;
# use scale < 1 to implement taxes
SCALE_MIN: float = 0.5
SCALE_MAX: float = 1.2

# HTTP status codes
# app is healthy and works well
STATUS_OK: int = status.HTTP_200_OK

# app fails due to invalid input data
STATUS_NOK: int = status.HTTP_400_BAD_REQUEST
