"""
Generic step profiler for measuring execution time of any code step.

Usage:
    from src.utils.step_profiler import step_profiler, profile_step

    # Option 1: Context manager
    with profile_step("my_module", "step_name"):
        # code to profile

    # Option 2: Decorator
    @profile_step("my_module", "my_function")
    def my_function():
        pass

    # Option 3: Manual timing
    step_profiler.record("my_module", "step_name", duration_seconds)
"""
import time
import logging
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Generator, TypeVar, Any
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# Generic step duration gauge - can be used for any module/step combination
STEP_DURATION = Gauge(
    "step_duration_seconds",
    "Duration of a step (last observed value)",
    ["module", "step"]
)


class StepProfiler:
    """Generic step profiler that records duration metrics."""

    def record(self, module: str, step: str, duration: float) -> None:
        """Record a step duration.
        
        Args:
            module: The module/component name (e.g., "batch_processor", "ingestor")
            step: The step name within the module (e.g., "filter_dataframe", "write_delta")
            duration: Duration in seconds
        """
        STEP_DURATION.labels(module=module, step=step).set(duration)

    @contextmanager
    def time_step(self, module: str, step: str) -> Generator[None, None, None]:
        """Context manager to time a step.
        
        Args:
            module: The module/component name
            step: The step name
            
        Example:
            with step_profiler.time_step("batch_processor", "write_delta"):
                write_to_delta(df)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.record(module, step, duration)


# Singleton instance
step_profiler = StepProfiler()


F = TypeVar('F', bound=Callable[..., Any])


def profile_step(module: str, step: str) -> Callable[[F], F]:
    """Decorator to profile a function.
    
    Args:
        module: The module/component name
        step: The step name (defaults to function name if not provided)
        
    Example:
        @profile_step("batch_processor", "apply_transformations")
        def apply_transformations(df):
            return transformed_df
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with step_profiler.time_step(module, step):
                return func(*args, **kwargs)
        return wrapper  # type: ignore
    return decorator
