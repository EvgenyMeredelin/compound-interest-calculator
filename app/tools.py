import io
import warnings
import uuid

import boto3
import matplotlib.pyplot as plt
import mplcyberpunk
from decouple import config

from .settings import (
    MPL_RUNTIME_CONFIG,
    S3_URL_LIFESPAN,
    # formatwarning
)

# select Anti-Grain Geometry backend to prevent "UserWarning:
# Starting a Matplotlib GUI outside of the main thread will likely fail."
# https://matplotlib.org/stable/users/explain/figure/backends.html#backends
plt.rcParams.update(MPL_RUNTIME_CONFIG)
plt.style.use("cyberpunk")
plt.switch_backend("agg")


bucket_name = config("S3_BUCKET_NAME")
tenant_id   = config("S3_TENANT_ID")
key_id      = config("S3_KEY_ID")

session = boto3.session.Session(
    aws_access_key_id=f"{tenant_id}:{key_id}",
    aws_secret_access_key=config("S3_KEY_SECRET"),
    region_name=config("S3_REGION_NAME")
)
client = session.client(
    service_name="s3",
    endpoint_url=config("S3_ENDPOINT_URL")
)

numeric = int | float
# warnings.formatwarning = formatwarning


def clamp(
    value: numeric, *, low: numeric, high: numeric, warn: bool = True
) -> numeric:
    """Clamp `value` to fit inclusive range [`low`, `high`]. """
    clamped_value = max(low, min(value, high))
    if warn and clamped_value in (low, high):
        warnings.warn(f"Ding-dong! {value} was clamped to {clamped_value}")
    return clamped_value


class Plotter:
    """
    Helper class to plot deposit balance progress chart and upload it to S3.
    """

    def __init__(self, schedule: dict[str, float]) -> None:
        self.schedule = schedule
        self.body = io.BytesIO()
        self._plot_chart()

    def _plot_chart(self) -> None:
        """Plot chart for provided interest schedule and save it as bytes. """
        # stretch chart depending on data
        data_size = len(self.schedule)
        fig, ax = plt.subplots(figsize=(data_size, 6))

        # plot bars and add amount labels
        dates, amounts = map(list, (self.schedule, self.schedule.values()))
        bars = plt.bar(dates, amounts, color="C3")
        mplcyberpunk.add_bar_gradient(bars=bars)
        label_size = 9 if amounts[0] < 100_000 else 8
        ax.bar_label(ax.containers[0], fmt="%.2f", size=label_size)

        # add xticks and title
        plt.xticks(rotation=90, ha="center")
        ax.tick_params(axis="x", pad=-55)
        ax.set_axisbelow(True)
        title_size = clamp(data_size * 3, low=15, high=72, warn=False)
        plt.title("Deposit balance progress", size=title_size)

        # save chart to bytes buffer
        plt.savefig(self.body, bbox_inches="tight", format="png")
        self.body.seek(0)
        plt.close(fig)

    def upload_chart(self) -> str:
        """Upload chart to S3 and return a limited time download link. """
        filename = str(uuid.uuid4()) + ".png"
        params = {
            "Bucket"     : "compound-interest-calculator",
            "Key"        : filename,
            "Body"       : self.body,
            "ContentType": "image/png"
        }
        client.put_object(**params)
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": "compound-interest-calculator",
                "Key"   : filename
            },
            ExpiresIn=S3_URL_LIFESPAN
        )
        return url
