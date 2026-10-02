"""BestBill: which electricity offer is cheapest for your own consumption."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bestbill")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled checkout
    __version__ = "0.0.0+unknown"
