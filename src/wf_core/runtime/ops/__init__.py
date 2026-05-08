"""Executor-only operations used by `wf_core.runtime`.

Root modules such as `wf_core.node_exec` remain as compatibility shims. New
runtime internals should import from this package so the execution seam stays
easy to navigate.
"""
