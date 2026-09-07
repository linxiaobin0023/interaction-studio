"""Run with python -m interaction_studio_api.studio_worker [--once]."""

import argparse
import logging
import signal
import threading

from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .db import make_session_factory
from .domain.studio_jobs import run_one


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Development rendering worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    factory = make_session_factory(settings.database_url)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO)
    while not stop.is_set():
        try:
            worked = run_one(factory, settings.artifact_root)
        except SQLAlchemyError:
            logging.error("STUDIO_WORKER_STORAGE_UNAVAILABLE")
            if args.once:
                raise SystemExit(1) from None
            stop.wait(5)
            continue
        if args.once:
            break
        if not worked:
            stop.wait(2)


if __name__ == "__main__":
    main()
