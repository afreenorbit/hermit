"""Hermit keeper — the small process that runs on each host's laptop.

It watches presence, claims and releases the ``soul`` role in Switch, cues the
host's own coding agent (the "brain"), writes the ledger and serves the critter.

Nothing in this package reaches for globals: every module takes its
dependencies through its constructor so that ``sim/`` and the tests can wire
fakes instead. ``cli.py`` is the only place that wires the real implementations.
"""

__version__ = "0.1.0"
