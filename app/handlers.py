__all__ = [
    "AmountHandler",
    "BypassAmountHandler",
    "FloorAmountHandler",
    "DateTime",
    "clamp"
]

# standard library
import datetime
import warnings
from abc import (
    ABC,
    abstractmethod
)
from typing import Self

# user modules
from .settings import (
    DATE_FORMAT,
    # formatwarning,
    SCALE_MIN,
    SCALE_MAX
)


numeric = int | float
# warnings.formatwarning = formatwarning


def clamp(
    value: numeric, *, low: numeric, high: numeric, warn: bool = True
) -> numeric:
    """
    Clamp `value` to fit inclusive range [`low`, `high`].
    """
    clamped_value = max(low, min(value, high))
    if warn and clamped_value in (low, high):
        warnings.warn(f"Ding-dong! {value} was clamped to {clamped_value}")
    return clamped_value


class DateTime(datetime.datetime):
    """
    `datetime.datetime` clone with parse method
    and modified informal string representation.
    """

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls.strptime(value, DATE_FORMAT)

    def __str__(self) -> str:
        return super().strftime(DATE_FORMAT)


class AmountHandler(ABC):
    """
    Abstract base class of amount handler.
    """

    def __init__(
        self,
        *,
        start_date: str | None = None,  # start of handler's validity period
        end_date: str | None = None,    # end of handler's validity period
        scale: float = 1.0              # amount multiplier/coefficient
    ) -> None:

        # validity period with no meaningful boundaries means "always valid"
        self.start_date = (
            DateTime.min if start_date is None
            else DateTime.parse(start_date)
        )
        self.end_date = (
            DateTime.max if end_date is None
            else DateTime.parse(end_date)
        )
        self.scale = clamp(scale, low=SCALE_MIN, high=SCALE_MAX)

    def handle(self, date: DateTime, amount: float) -> float:
        """
        Multiply `amount` by a `scale` factor if `date` is in the handler's
        validity period.
        """
        if self.scale != 1 and self.start_date <= date <= self.end_date:
            amount *= self.scale
        return self.__class__.handle_cents(amount)

    @staticmethod
    @abstractmethod
    def handle_cents(amount: float) -> float:
        """
        Define a logic to handle cents.
        """
        raise NotImplementedError


class BypassAmountHandler(AmountHandler):
    @staticmethod
    def handle_cents(amount: float) -> float:
        """
        Return `amount` as-is, with no processing applied.
        """
        return amount


class FloorAmountHandler(AmountHandler):
    @staticmethod
    def handle_cents(amount: float) -> float:
        """
        Floor `amount` to a full cent, e.g. 0.(9) -> 0.99.
        """
        return int(amount * 100) / 100
