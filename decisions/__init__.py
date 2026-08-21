"""Decision slices — one package per FPL manager-facing decision.

This file contains a module docstring and nothing else, and must stay that way. A single
import here executes for *every* importer of *every* module in every slice below it, which
would give the model-free modules a transitive `model/` dependency that no per-module import
contract could see. See `starting_xi/DESIGN.md` §5.6.
"""
