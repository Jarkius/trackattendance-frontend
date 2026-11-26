"""Shared pytest setup.

Load onnxruntime before any test imports PyQt6: PyQt6 ships an old MSVC runtime and
onnxruntime imported after it crashes the interpreter on Windows (main.py does the same).
"""
try:
    import onnxruntime  # noqa: F401
except Exception:
    pass
