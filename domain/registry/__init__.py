"""Registry contract + consume-side runtime primitives.

This package is the *consume side* of signal governance (the decide side —
authoring decisions, promoting, mutating lifecycle state — lives in
``model/governance/``). It holds two kinds of thing:

  Contract (meaning):
    schema.py            registry column contract + controlled vocabularies
    validation.py        enforces the contract

  Runtime consumption primitives (mechanism every consumer may import):
    loader.py            pure typed CSV loader
    operational.py       loader + lifecycle gate, for operational consumers
    lifecycle.py         assert_operational_safe — the path-based runtime gate

These primitives live in ``domain`` — the shared leaf — not because ``domain``
owns governance, but because ``serve`` must consume governed artifacts at runtime
and may not import ``model`` (``no_serve_to_research_or_model``). Reading a
decision is not making one; authority remains in ``model/governance/``.
"""
