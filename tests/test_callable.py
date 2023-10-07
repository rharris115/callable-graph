from typing import Callable, Any
import pytest

from callable_graph.callable import LeftComposition, CallableGraph


@pytest.mark.parametrize(
    argnames=["funcs", "input", "expected"],
    argvalues=[
        ((str, hash), 1, hash(str(1))),
        ((lambda x: x // 2, str), 3, str(3 // 2)),
        ((str, lambda l: 8 * l), 10, 8 * "10"),
    ],
)
def test_left_composition(funcs: tuple[Callable], input: Any, expected: Any):
    composition = LeftComposition(*funcs)
    actual = composition(input)
    assert actual == expected


@pytest.mark.parametrize(
    argnames=["graph", "kwargs", "expected"],
    argvalues=[
        (
            CallableGraph.builder()
            .with_edge(hash, str, inputs="input", outputs="output")
            .build(),
            dict(input="hello"),
            {"input": "hello", "output": str(hash("hello"))},
        ),
        (
            CallableGraph.builder()
            .with_edge(hash, inputs="input", outputs="output_0")
            .with_edge(lambda x: f"{x} world", inputs="input", outputs="output_1")
            .build(),
            dict(input="hello"),
            {"input": "hello", "output_0": hash("hello"), "output_1": "hello world"},
        ),
    ],
)
def test_callable_graph(
    graph: CallableGraph, kwargs: dict[str, Any], expected: dict[str, Any]
):
    actual = graph(**kwargs)
    assert actual == expected


def test_left_composition_exception():
    def exception_thrower(hashed: int):
        raise Exception()

    composition = LeftComposition(hash, exception_thrower, str)

    with pytest.raises(Exception):
        composition("input")


def test_left_composition_exception_no_side_effects():
    def exception_thrower(hashed: int):
        if hashed == hash("bad"):
            raise Exception()
        return hashed

    composition = LeftComposition(hash, exception_thrower, str)

    # Call the composition so that an exception is raised.
    with pytest.raises(Exception):
        composition("bad")

    # Call the composition normally.
    ret = composition("good")
