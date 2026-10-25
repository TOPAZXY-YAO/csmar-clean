"""Exception types raised by csmar-clean."""


class CleanError(Exception):
    """A cleaning step failed on the input data (e.g. a required column is missing)."""


class RuleError(Exception):
    """The rule configuration (default or user YAML) is invalid."""
