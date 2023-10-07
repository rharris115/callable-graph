from dataclasses import dataclass
from typing import (
    Callable,
    Any,
    Sequence,
)


def _pipe(
    *funcs: Callable,
    args: tuple = (),
    kwargs: dict[str, Any] = None,
) -> Any:
    if kwargs is None:
        kwargs = {}

    if not funcs:
        raise ValueError("No functions specified.")

    first, *rest = funcs

    ret = first(*args, **kwargs)

    for func in rest:
        ret = func(ret)

    return ret


class LeftComposition:
    """
    A function composition that returns function timings along with results.
    """

    def __init__(self, *funcs: Callable):
        self.funcs = funcs

    def __call__(self, *args, **kwargs) -> Any:
        return _pipe(*self.funcs, args=args, kwargs=kwargs)


class CallableGraph:
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
        subgraph_name: str | None

    class Builder:
        def __init__(self):
            self._edges: list[CallableGraph.Edge] = []
            self._returned_outputs: tuple[str] = ()

        def with_edge(
            self,
            *funcs: Callable,
            inputs: str | Sequence[str],
            outputs: str | Sequence[str],
            subgraph_name: str | None = None,
        ) -> "CallableGraph.Builder":
            """
            Add an edge to the graph.

            :param funcs: a function or sequence of functions to be applied to the inputs and saved to the outputs
            :param inputs: the inputs
            :param outputs: the outputs
            :param subgraph_name: the subgroup of the edge
            :return: the graph builder
            """
            if not funcs:
                raise ValueError("No functions specified.")

            if isinstance(inputs, str):
                inputs = [inputs]
            if isinstance(outputs, str):
                outputs = [outputs]

            outputs_set = {*outputs}
            for edge in self._edges:
                if overwritten_outputs := outputs_set.intersection(edge.outputs):
                    raise ValueError(
                        f"Outputs cannot be re-calculated. re-calculated = {overwritten_outputs}"
                    )

            self._edges.append(
                CallableGraph.Edge(
                    funcs=funcs,
                    inputs=tuple(inputs),
                    outputs=tuple(outputs),
                    subgraph_name=subgraph_name,
                )
            )
            return self

        def with_subgraph(
            self, other: "CallableGraph.Builder", name: str
        ) -> "CallableGraph.Builder":
            """
            Add all the edges of another sub-graph's builder. This subgraph must not have special returned outputs (tuple return).
            :param other: the other sub-graph builder
            :return: the graph builder
            """
            if other._returned_outputs:
                raise ValueError(
                    "The sub-graph must have no special returned outputs. other._returned_outputs={other._returned_outputs}"
                )

            for edge in other._edges:
                self.with_edge(
                    *edge.funcs,
                    inputs=edge.inputs,
                    outputs=edge.outputs,
                    subgraph_name=name,
                )

            return self

        def and_return(self, *outputs: str) -> "CallableGraph.Builder":
            """
            Specify which nodes the graph is to return. If no specification is made a dictionary of all nodes to their associated data
            will be returns when the graph is called.

            If a single output is specified, the graph will return the value referenced by that string node. If more than one
            is specified, the graph will return a tuple of those values in the order specified here.

            :param outputs: those nodes that the built graph will return
            :return: the graph builder
            """
            all_nodes_set = {
                node for edge in self._edges for node in {*edge.inputs, *edge.outputs}
            }

            outputs_set = {*outputs}
            if not outputs_set.issubset(all_nodes_set):
                raise ValueError(f"Outputs not present, {outputs_set - all_nodes_set}.")

            self._returned_outputs = outputs

            return self

        def build(self) -> "CallableGraph":
            """
            Build the graph.

            :return: the built graph
            """
            return CallableGraph(*self._edges, returned_outputs=self._returned_outputs)

    def __init__(self, *edges: Edge, returned_outputs: tuple[str]):
        self._edges = edges
        self._inputs = frozenset(input for edge in edges for input in edge.inputs)
        self._outputs = frozenset(output for edge in edges for output in edge.outputs)
        self._returned_outputs = returned_outputs

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
    def builder() -> "CallableGraph.Builder":
        return CallableGraph.Builder()

    def __call__(self, **kwargs: Any) -> dict[str, Any] | tuple | Any:
        if missing_kwargs := self.required_kwargs - {*kwargs.keys()}:
            raise ValueError(f"Missing key word arguments {missing_kwargs}.")

        edges_to_process: set[CallableGraph.Edge] = {*self._edges}
        data = {**kwargs}

        while edges_to_process:
            processed_edges = set()
            for edge in edges_to_process:
                if {*edge.inputs}.issubset(data):
                    ret = _pipe(
                        *edge.funcs, args=tuple(data[input] for input in edge.inputs)
                    )
                    if len(edge.outputs) == 1:
                        data[edge.outputs[0]] = ret
                    elif len(edge.outputs) > 1:
                        data |= zip(edge.outputs, ret)
                    processed_edges.add(edge)

            edges_to_process.difference_update(processed_edges)

        if len(self._returned_outputs) == 1:
            return data[self._returned_outputs[0]]
        elif self._returned_outputs:
            return tuple(data[output] for output in self._returned_outputs)
        else:
            return data
