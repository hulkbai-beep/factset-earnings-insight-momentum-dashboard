"""Dashboard page renderers."""

from .analyst_sentiment import render as render_analyst_sentiment
from .data_quality import render as render_data_quality
from .guidance_quality import render as render_guidance_quality
from .market_regime import render as render_market_regime
from .revision_movers import render as render_revision_movers
from .sector_leadership import render as render_sector_leadership
from .sector_quality import render as render_sector_quality
from .sector_trends import render as render_sector_trends


__all__ = [
    "render_market_regime",
    "render_sector_leadership",
    "render_sector_trends",
    "render_sector_quality",
    "render_guidance_quality",
    "render_revision_movers",
    "render_analyst_sentiment",
    "render_data_quality",
]
