"""Thin wrapper to reuse the project-level signal logger from utils package imports."""


from signal_logger import get_signal_logger


signal_logger = get_signal_logger()


__all__ = ["signal_logger", "get_signal_logger"]
