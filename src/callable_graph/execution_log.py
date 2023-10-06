import functools
import traceback
from time import process_time
from typing import Optional, Callable, Any, Union

from pydantic import BaseModel

from .callable import LeftCompositionWithTimings, CallableGraphWithTimings


def function_str(function: Callable) -> str:
    if not hasattr(function, "__qualname__"):
        return str(function)
    return function.__qualname__


class ComponentInfo(BaseModel):
    name: str
    execution_time: float

    @classmethod
    def adapt(cls, execution_times: list[tuple[Callable, float]]):
        """
        Adapts the execution times to a list of `ComponentInfo` instances.
        :param execution_times:  the list of execution times
        :return: the adapted List of component infos
        """
        return [
            cls(name=function_str(f), execution_time=elapsed)
            for f, elapsed in execution_times
        ]


class ExecutionLog(BaseModel):
    success: bool
    execution_time: float
    component_info: list[ComponentInfo]
    exception: Optional[str] = None

    @classmethod
    def logged(
        cls, callable: Union[LeftCompositionWithTimings, CallableGraphWithTimings]
    ) -> Callable[..., tuple[Any, "ExecutionLog"]]:
        """
        Modifies the specified `CallableWithCallbacks` to return its results and an `ExecutionLog` log.

        :param callable: the `CallableWithCallbacks` to be logged
        :return: a new callable that return a tuple of its result and a log of it's execution
        """

        @functools.wraps(callable)
        def _wrapper(*args: Any, **kwargs: Any) -> tuple[Any, ExecutionLog]:

            start = process_time()

            try:
                ret, execution_times = callable(*args, **kwargs)
                return ret, cls(
                    success=True,
                    execution_time=process_time() - start,
                    component_info=ComponentInfo.adapt(execution_times=execution_times),
                    exception=None,
                )
            except Exception:
                tb = traceback.format_exc()
                return None, cls(
                    success=False,
                    execution_time=process_time() - start,
                    component_info=[],
                    exception=tb,
                )

        return _wrapper
