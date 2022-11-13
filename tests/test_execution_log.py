from akita_callable.callable import LeftCompositionWithTimings, CallableGraphWithTimings
from akita_callable.execution_log import ExecutionLog


def test_execution_log_for_left_composition():
    composition = ExecutionLog.logged(callable=LeftCompositionWithTimings(hash, str))

    ret, log = composition("hello")

    expected_function_strs = [
        hash.__qualname__,
        str.__qualname__,
    ]

    assert log.success
    assert log.execution_time > 0
    assert log.exception is None

    for actual_component_info, expected_str in zip(
        log.component_info, expected_function_strs
    ):
        assert actual_component_info.name == expected_str
        assert actual_component_info.execution_time > 0


def test_execution_log_for_callable_graph():
    graph = ExecutionLog.logged(
        CallableGraphWithTimings.builder()
        .with_edge(hash, str, inputs="input", outputs="output")
        .build()
    )

    ret, log = graph(input="hello")

    expected_function_reprs = [
        hash.__qualname__,
        str.__qualname__,
    ]

    assert log.success
    assert log.execution_time > 0
    assert log.exception is None

    for actual_component_info, expected_repr in zip(
        log.component_info, expected_function_reprs
    ):
        assert actual_component_info.name == expected_repr
        assert actual_component_info.execution_time > 0
