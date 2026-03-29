"""Queue Layer - Event streaming and processing"""
# Intentionally empty — no eager imports.
# Importing from this package at module-load time shadows Python's stdlib
# `queue` module and breaks concurrent.futures / anyio / starlette.
# Import submodules directly where needed, e.g.:
#   from email_queue.producer.event_producer import EventProducer
