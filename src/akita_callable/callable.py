from contextlib import AbstractContextManager
from dataclasses import dataclass
from time import perf_counter
from typing import (
    Callable,
    Any,
    Union,
    Sequence,
    Optional,
)


class _ReusableTimer(AbstractContextManager):
    def __init__(self):
        self._start: Optional[float] = None
        self._elapsed: Optional[float] = None

    def __enter__(self):
        assert self._start == None, "_start is not None."

        self._start = perf_counter()
        self._elapsed = None

        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self._start != None, "_start is None."

        self._elapsed = perf_counter() - self._start
        self._start = None

    @property
    def elapsed(self) -> Optional[float]:
        return self._elapsed


def _pipe(
    *funcs: Callable,
    args: tuple = tuple(),
    kwargs: dict[str, Any] = None,
) -> tuple[Any, list[tuple[Callable, float]]]:
    if kwargs is None:
        kwargs = {}

    assert len(funcs) > 0, "No functions specified."

    execution_times: list[tuple[Callable, float]] = []

    first, *rest = funcs

    timer = _ReusableTimer()

    with timer:
        ret = first(*args, **kwargs)
    execution_times.append((first, timer.elapsed))

    for func in rest:
        with timer:
            ret = func(ret)
        execution_times.append((func, timer.elapsed))

    return ret, execution_times


class LeftCompositionWithTimings:
    """
    A function composition that returns function timings along with results.
    """

    def __init__(self, *funcs: Callable):
        super().__init__()
        self.funcs = funcs

    def __call__(self, *args, **kwargs) -> tuple[Any, list[tuple[Callable, float]]]:
        return _pipe(*self.funcs, args=args, kwargs=kwargs)


class CallableGraphWithTimings:
    """
    A graph that is callable. Each node serves as a string reference to either a keyword input or an intermediate or
    final output. Each edge is a function or composition of functions that are applied to specific nodes to produce
    specific output nodes. This graph is callable where each call will return a log of execution times along with the final
    results.
    """

    @dataclass(frozen=True, repr=True)
    class Edge:
        funcs: tuple[Callable, ...]
        inputs: tuple[str]
        outputs: tuple[str]
        subgraph_name: Optional[str]

    class Builder:
        def __init__(self):
            self._edges: list[CallableGraphWithTimings.Edge] = []
            self._returned_outputs: tuple[str] = tuple()

        def with_edge(
            self,
            *funcs: Callable,
            inputs: Union[str, Sequence[str]],
            outputs: Union[str, Sequence[str]],
            subgraph_name: Optional[str] = None,
        ) -> "CallableGraphWithTimings.Builder":
            """
            Add an edge to the graph.

            :param funcs: a function or sequence of functions to be applied to the inputs and saved to the outputs
            :param inputs: the inputs
            :param outputs: the outputs
            :param subgraph_name: the subgroup of the edge
            :return: the graph builder
            """
            assert len(funcs) > 0, "No functions specified."

            if isinstance(inputs, str):
                inputs = [inputs]
            if isinstance(outputs, str):
                outputs = [outputs]

            outputs_set = {*outputs}
            for edge in self._edges:
                overwritten_outputs = outputs_set.intersection(edge.outputs)
                assert (
                    not overwritten_outputs
                ), f"Outputs cannot be re-calculated. re-calculated = {overwritten_outputs}"

            self._edges.append(
                CallableGraphWithTimings.Edge(
                    funcs=funcs,
                    inputs=tuple(inputs),
                    outputs=tuple(outputs),
                    subgraph_name=subgraph_name,
                )
            )
            return self

        def with_subgraph(
            self, other: "CallableGraphWithTimings.Builder", name: str
        ) -> "CallableGraphWithTimings.Builder":
            """
            Add all the edges of another sub-graph's builder. This subgraph must not have special returned outputs (tuple return).
            :param other: the other sub-graph builder
            :return: the graph builder
            """
            assert (
                not other._returned_outputs
            ), f"The sub-graph must have no special returned outputs. other._returned_outputs={other._returned_outputs}"

            for edge in other._edges:
                self.with_edge(
                    *edge.funcs,
                    inputs=edge.inputs,
                    outputs=edge.outputs,
                    subgraph_name=name,
                )

            return self

        def and_return(self, *outputs: str) -> "CallableGraphWithTimings.Builder":
            """
            Specify which nodes the graph is to return. If no specification is made a dictionary of all nodes to their associated data
            will be returns when the graph is called.

            If a single output is specified, the graph will return the value referenced by that string node. If more than one
            is specified, the graph will return a tuple of those values in the order specified here.

            :param outputs: those nodes that the built graph will return
            :return: the graph builder
            """
            outputs_set = {*outputs}
            all_nodes_set = {
                node for edge in self._edges for node in {*edge.inputs, *edge.outputs}
            }
            assert outputs_set.issubset(
                all_nodes_set
            ), f"Outputs not present, {outputs_set - all_nodes_set}."

            self._returned_outputs = outputs

            return self

        def build(self) -> "CallableGraphWithTimings":
            """
            Build the graph.

            :return: the built graph
            """
            return CallableGraphWithTimings(
                *self._edges, returned_outputs=self._returned_outputs
            )

    def __init__(self, *edges: Edge, returned_outputs: tuple[str]):
        super().__init__()

        self._edges = edges

        self._inputs: frozenset[str] = frozenset(
            input for edge in edges for input in edge.inputs
        )
        self._outputs: frozenset[str] = frozenset(
            output for edge in edges for output in edge.outputs
        )

        self._returned_outputs: tuple[str] = returned_outputs

    @property
    def inputs(self) -> frozenset[str]:
        return self._inputs

    @property
    def outputs(self) -> frozenset[str]:
        return self._outputs

    @property
    def returned_outputs(self) -> tuple[str]:
        return self._returned_outputs

    @property
    def edges(self) -> tuple[Edge]:
        return self._edges

    @property
    def required_kwargs(self) -> frozenset[str]:
        return self._inputs.difference(self._outputs)

    @property
    def terminal_outputs(self) -> frozenset[str]:
        return self._outputs.difference(self._inputs)

    @staticmethod
    def builder() -> "CallableGraphWithTimings.Builder":
        return CallableGraphWithTimings.Builder()

    def __call__(
        self, **kwargs: Any
    ) -> tuple[Union[dict[str, Any], tuple, Any], list[tuple[Callable, float]]]:
        kwarg_keys = {*kwargs.keys()}
        _required_kwargs = self.required_kwargs

        missing_kwargs = _required_kwargs.difference(kwarg_keys)
        assert not missing_kwargs, f"Missing key word arguments {missing_kwargs}."

        edges_to_process: set[CallableGraphWithTimings.Edge] = {*self._edges}
        data = {**kwargs}

        execution_times = []

        while edges_to_process:
            processed_edges = set()
            for edge in edges_to_process:
                if {*edge.inputs}.issubset(data.keys()):

                    ret, pipe_execution_times = _pipe(
                        *edge.funcs, args=tuple(data[input] for input in edge.inputs)
                    )

                    if len(edge.outputs) == 1:
                        data[edge.outputs[0]] = ret
                    elif len(edge.outputs) > 1:
                        data.update(zip(edge.outputs, ret))

                    processed_edges.add(edge)
                    execution_times += pipe_execution_times

            edges_to_process.difference_update(processed_edges)

        if len(self._returned_outputs) == 1:
            return data[self._returned_outputs[0]], execution_times
        elif self._returned_outputs:
            return (
                tuple(data[output] for output in self._returned_outputs),
                execution_times,
            )
        else:
            return data, execution_times
