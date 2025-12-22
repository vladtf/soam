#!/usr/bin/env python
"""Wrapper script to run uvicorn - used for profiling with scalene."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000)
