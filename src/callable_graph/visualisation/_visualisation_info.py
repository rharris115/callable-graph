import inspect
from collections import defaultdict
from enum import Enum
from typing import get_args, get_origin, Optional
from colour import Color
from callable_graph.callable import CallableGraph
from typing import Callable


def function_str(function: Callable) -> str:
    if not hasattr(function, "__qualname__"):
        return str(function)
    return function.__qualname__


class Orientation(str, Enum):
    """
    An enum to specify the orientation of callable graph visualisations.
    """

    TOP_TO_BOTTOM = "TB"
    BOTTOM_TO_TOP = "BT"
    RIGHT_TO_LEFT = "RL"
    LEFT_TO_RIGHT = "LR"


class StyleClass(str, Enum):
    KEYWORD = "ks"
    INTERMEDIATE = "is"
    TERMINAL = "ts"
    SUBGRAPH = "ss"
    FUNCTION = "fs"
    RETURNED = "rs"

    @staticmethod
    def resolve_data_node(data_node: str, graph: CallableGraph):
        if data_node in graph.returned_outputs:
            return StyleClass.RETURNED
        elif data_node in graph.required_kwargs:
            return StyleClass.KEYWORD
        elif data_node in graph.terminal_outputs:
            return StyleClass.TERMINAL
        else:
            return StyleClass.INTERMEDIATE


class ColorCalculator:
    DEFAULT_STYLE_COLOURS: dict[StyleClass, str] = {
        StyleClass.KEYWORD: "green",
        StyleClass.INTERMEDIATE: "yellow",
        StyleClass.TERMINAL: "red",
        StyleClass.SUBGRAPH: "cyan",
        StyleClass.FUNCTION: "blue",
        StyleClass.RETURNED: "red",
    }

    DEFAULT_STYLE_ALPHAS: dict[StyleClass, float] = {
        StyleClass.KEYWORD: 0.05,
        StyleClass.INTERMEDIATE: 0.05,
        StyleClass.TERMINAL: 0.05,
        StyleClass.SUBGRAPH: 0.05,
        StyleClass.FUNCTION: 0.05,
        StyleClass.RETURNED: 0.5,
    }

    def __init__(
        self,
        colours: Optional[dict[StyleClass, str]] = None,
        alphas: Optional[dict[StyleClass, float]] = None,
    ):
        colours = (colours or {}) | ColorCalculator.DEFAULT_STYLE_COLOURS
        alphas = (alphas or {}) | ColorCalculator.DEFAULT_STYLE_ALPHAS

        self.calculated_colours = {
            style_class: Color(colours[style_class]).hex_l
            + ColorCalculator.to_alpha_hex(alpha=alphas[style_class])
            for style_class in StyleClass
        }

    def __getitem__(self, style_class: StyleClass) -> str:
        return self.calculated_colours[style_class]

    @staticmethod
    def to_alpha_hex(alpha: float) -> str:
        assert 0 <= alpha <= 1, f"The alpha value in range[0, 1]."
        return hex(int(255 * alpha))[2:].rjust(2, "0")


class SubgraphInfo:
    def __init__(
        self,
        top_level_data_nodes: set[str],
        subgraph_inputs: dict[str, set[str]],
        subgraph_outputs: dict[str, set[str]],
    ):
        self._top_level_data_nodes = frozenset(top_level_data_nodes)
        self._subgraph_inputs = {
            subgraph_name: frozenset(data_nodes)
            for subgraph_name, data_nodes in subgraph_inputs.items()
        }
        self._subgraph_outputs = {
            subgraph_name: frozenset(data_nodes)
            for subgraph_name, data_nodes in subgraph_outputs.items()
        }

    @property
    def top_level_data_nodes(self) -> frozenset[str]:
        return self._top_level_data_nodes

    @property
    def subgraph_inputs(self) -> dict[str, frozenset[str]]:
        return self._subgraph_inputs

    @property
    def subgraph_outputs(self) -> dict[str, frozenset[str]]:
        return self._subgraph_outputs

    @property
    def subgraphs(self) -> frozenset[str]:
        return frozenset((self._subgraph_inputs | self._subgraph_outputs).keys())

    @classmethod
    def from_graph(cls, graph: CallableGraph) -> "SubgraphInfo":
        subgraph_data_nodes = defaultdict(set)
        data_node_subgraphs = defaultdict(set)
        for edge in graph.edges:
            subgraph_data_nodes[edge.subgraph_name] |= {*edge.inputs, *edge.outputs}
            for data_node in edge.inputs + edge.outputs:
                data_node_subgraphs[data_node].add(edge.subgraph_name)

        data_nodes_in_multiple_subgraphs = {
            data_node
            for data_node, subgraphs in data_node_subgraphs.items()
            if len(subgraphs - {None}) > 1
        }

        top_level_data_nodes = (
            subgraph_data_nodes[None]
            | graph.required_kwargs
            | graph.terminal_outputs
            | data_nodes_in_multiple_subgraphs
        )

        subgraph_inputs, subgraph_outputs = defaultdict(set), defaultdict(set)
        for edge in graph.edges:
            if edge.subgraph_name is not None:
                subgraph_inputs[edge.subgraph_name] |= {
                    *edge.inputs
                } & top_level_data_nodes
                subgraph_outputs[edge.subgraph_name] |= {
                    *edge.outputs
                } & top_level_data_nodes

        return cls(
            top_level_data_nodes,
            subgraph_inputs=subgraph_inputs,
            subgraph_outputs=subgraph_outputs,
        )


class TypeNames:
    BUILTIN_FUNCTIONS_WITH_KNOWN_OUTPUTS = {
        all: bool,
        any: bool,
        ascii: int,
        bin: str,
        bytes: bytes,
        callable: bool,
        chr: str,
        divmod: tuple[int, int],
        format: str,
        hash: int,
        hex: str,
        id: int,
        isinstance: bool,
        issubclass: bool,
        len: int,
        oct: str,
        ord: int,
        repr: str,
        sorted: list,
    }

    def __init__(self, types_by_data_node: dict[str, set[type]]):
        self.types_by_data_node = types_by_data_node

    def __call__(self, data_node: str) -> str:
        types = self.types_by_data_node.get(data_node, [])
        return ", ".join(map(TypeNames._type_name, types))

    @staticmethod
    def _type_name(t: type) -> str:
        if isinstance(t, str):
            return t
        elif hasattr(t, "__name__"):
            return t.__name__
        return str(t)

    @classmethod
    def from_graph(cls, graph: CallableGraph):
        types_by_data_node = defaultdict(set)
        for edge in graph.edges:
            for data_node, t in TypeNames._infer_input_types(edge=edge).items():
                types_by_data_node[data_node].add(t)
            for data_node, t in TypeNames._infer_output_types(edge=edge).items():
                types_by_data_node[data_node].add(t)
        return cls(types_by_data_node=types_by_data_node)

    @staticmethod
    def _infer_input_types(edge: CallableGraph.Edge) -> dict[str, type]:
        first = edge.funcs[0]

        if inspect.isbuiltin(first):
            return {}

        try:
            sig = inspect.signature(first)
        except ValueError:
            return {}

        input_types = {}

        # Deal with position params.
        positional_params = [
            p
            for _, p in sig.parameters.items()
            if p.kind
            in {
                p.POSITIONAL_ONLY,
                p.POSITIONAL_OR_KEYWORD,
            }
            and p.default is inspect.Parameter.empty
        ]

        for i, p in zip(edge.inputs[: len(positional_params)], positional_params):
            if p.annotation is not inspect.Parameter.empty:
                input_types[i] = p.annotation

        # Deal with var, or *, params.
        var_positional_params = [
            p for _, p in sig.parameters.items() if p.kind == p.VAR_POSITIONAL
        ]

        if len(var_positional_params) == 1:
            p = var_positional_params[0]
            for i in edge.inputs[len(positional_params) :]:
                if p.annotation is not inspect.Parameter.empty:
                    input_types[i] = p.annotation

        return input_types

    @staticmethod
    def _infer_output_types(edge: CallableGraph.Edge) -> dict[str, type]:
        last = edge.funcs[-1]
        if inspect.isclass(last) and len(edge.outputs) == 1:
            return {edge.outputs[0]: last}
        elif (
            last in TypeNames.BUILTIN_FUNCTIONS_WITH_KNOWN_OUTPUTS
            and len(edge.outputs) == 1
        ):
            return {
                edge.outputs[0]: TypeNames.BUILTIN_FUNCTIONS_WITH_KNOWN_OUTPUTS[last]
            }
        elif inspect.isbuiltin(last):
            return {}
        else:
            sig = inspect.signature(last)
            if (
                sig.return_annotation is None
                or sig.return_annotation is inspect.Parameter.empty
            ):
                return {}

            if len(edge.outputs) == 1:
                return {edge.outputs[0]: sig.return_annotation}

            if get_origin(sig.return_annotation) is tuple and len(edge.outputs) > 1:
                return {
                    o: t for o, t in zip(edge.outputs, get_args(sig.return_annotation))
                }
