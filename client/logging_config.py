from __future__ import annotations

import logging
import os
import sys


def setup_logging() -> logging.Logger:
    custom_log = os.getenv("TOKENHUB_LOG")
    if custom_log:
        log_file = os.path.expanduser(custom_log)
    else:
        pid = os.getpid()
        log_file = os.path.expanduser(f"~/tokenhub_{pid}.log")

    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | [PID:%(process)d] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    logger = logging.getLogger("tokenhub")
    logger.setLevel(logging.DEBUG)

    if os.getenv("TOKENHUB_DEBUG"):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info("TokenHub client starting")
    logger.info(f"PID: {os.getpid()}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 50)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    if name is None or name == "tokenhub":
        return logging.getLogger("tokenhub")
    return logging.getLogger(f"tokenhub.{name}")


_logger = setup_logging()
