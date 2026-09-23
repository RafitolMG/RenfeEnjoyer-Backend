from enum import StrEnum


class JobState(StrEnum):
    STARTING = "starting"
    LOGGING_IN = "logging_in"
    OPENING_PASS = "opening_pass"
    AWAITING_CODE = "awaiting_code"
    SEARCHING = "searching"
    POLLING = "polling"
    RESERVED = "reserved"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset({JobState.FINISHED, JobState.FAILED, JobState.CANCELLED})
