from typing import Callable, Tuple, Any, Dict

import pytest

from callable_graph.callable import LeftCompositionWithTimings, CallableGraphWithTimings


@pytest.mark.parametrize(
    argnames=["funcs", "input", "expected"],
    argvalues=[
        ((str, hash), 1, hash(str(1))),
        ((lambda x: x // 2, str), 3, str(3 // 2)),
        ((str, lambda l: 8 * l), 10, 8 * "10"),
    ],
)
def test_left_composition(funcs: Tuple[Callable], input: Any, expected: Any):
    composition = LeftCompositionWithTimings(*funcs)
    actual, execution_times = composition(input)
    assert actual == expected
    for f, (actual_f, elapsed) in zip(funcs, execution_times):
        assert f == actual_f
        assert elapsed >= 0


@pytest.mark.parametrize(
    argnames=["graph", "kwargs", "expected"],
    argvalues=[
        (
            CallableGraphWithTimings.builder()
            .with_edge(hash, str, inputs="input", outputs="output")
            .build(),
            dict(input="hello"),
            {"input": "hello", "output": str(hash("hello"))},
        ),
        (
            CallableGraphWithTimings.builder()
            .with_edge(hash, inputs="input", outputs="output_0")
            .with_edge(lambda x: x + " world", inputs="input", outputs="output_1")
            .build(),
            dict(input="hello"),
            {"input": "hello", "output_0": hash("hello"), "output_1": "hello world"},
        ),
    ],
)
def test_callable_graph(
    graph: CallableGraphWithTimings, kwargs: Dict[str, Any], expected: Dict[str, Any]
):
    actual, execution_times = graph(**kwargs)
    assert actual == expected


def test_left_composition_exception():
    def exception_thrower(hashed: int):
        raise Exception()

    composition = LeftCompositionWithTimings(hash, exception_thrower, str)

    with pytest.raises(Exception):
        composition("input")


def test_left_composition_exception_no_side_effects():
    def exception_thrower(hashed: int):
        if hashed == hash("bad"):
            raise Exception()
        return hashed

    composition = LeftCompositionWithTimings(hash, exception_thrower, str)

    # Call the composition so that an exception is raised.
    with pytest.raises(Exception):
        composition("bad")

    # Call the composition normally.
    ret, execution_times = composition("good")

    for f, (execution_times_f, elapsed) in zip(composition.funcs, execution_times):
        assert f == execution_times_f
        assert elapsed >= 0
