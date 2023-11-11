from io import TextIOWrapper

from callable_graph.callable import CallableGraph
from callable_graph.visualisation._visualisation_info import (
    function_str,
    Orientation,
    SubgraphInfo,
    TypeNames,
    StyleClass,
    ColorCalculator,
)


class FunctionLabeller:
    def __init__(self):
        self.labeled = set()

    def __call__(self, edge_index: int, f_index: int, f) -> str:
        if (edge_index, f_index) in self.labeled:
            return f"f_{edge_index}_{f_index}"
        self.labeled.add((edge_index, f_index))
        return (
            f'f_{edge_index}_{f_index}(["{function_str(f)}"]):::{StyleClass.FUNCTION}'
        )


class DataNodeLabeller:
    def __init__(self, graph: CallableGraph):
        self.graph = graph
        self.labelled = set()
        self.type_names = TypeNames.from_graph(graph=graph)

    def __call__(self, data_node: str) -> str:
        if data_node in self.labelled:
            return f"dn_{data_node}"

        self.labelled.add(data_node)

        type_string = self.type_names(data_node=data_node)
        type_string = ": " + type_string if type_string else ""
        return f'dn_{data_node}["{data_node}{type_string}"]:::{StyleClass.resolve_data_node(data_node=data_node,graph=self.graph)}'


class SubgraphLabeller:
    def __init__(self):
        self.labelled = set()

    def __call__(self, subgraph_name: str) -> str:
        sg_node = "_".join(subgraph_name.split()).lower()
        if sg_node in self.labelled:
            return f"sg_{sg_node}"
        self.labelled.add(subgraph_name)
        return f'sg_{sg_node}{{{{"{subgraph_name}"}}}}:::{StyleClass.SUBGRAPH}'


def to_mermaid(
    graph: CallableGraph,
    out: TextIOWrapper,
    orientation: Orientation = Orientation.LEFT_TO_RIGHT,
    colours: dict[StyleClass, str] | None = None,
    alphas: dict[StyleClass, float] | None = None,
):
    subgraph_info = SubgraphInfo.from_graph(graph=graph)

    function_labeller = FunctionLabeller()
    data_node_labeller = DataNodeLabeller(graph=graph)
    subgraph_labeller = SubgraphLabeller()

    out.write(f"graph {orientation.value}\n")
    out.write("\n")

    out.write("  %% Subgraph Edges\n")
    for subgraph_name, inputs in subgraph_info.subgraph_inputs.items():
        for input in inputs:
            out.write(
                f"  {data_node_labeller(data_node=input)} -.-> {subgraph_labeller(subgraph_name=subgraph_name)}\n"
            )

    for subgraph_name, outputs in subgraph_info.subgraph_outputs.items():
        for output in outputs:
            out.write(
                f"  {subgraph_labeller(subgraph_name=subgraph_name)} -.-> {data_node_labeller(data_node=output)}\n"
            )
    out.write("\n")

    out.write("  %% Top Level Edges\n")
    for edge_index, edge in enumerate(graph.edges):
        if edge.subgraph_name is not None:
            continue

        functions_and_indexes = list(enumerate(edge.funcs))

        f_index_start, f_start = functions_and_indexes[0]
        for input in edge.inputs:
            out.write(
                f"  {data_node_labeller(data_node=input)} --> {function_labeller(edge_index=edge_index, f_index=f_index_start, f=f_start)}\n"
            )

        for (idx1, f1), (idx2, f2) in zip(
            functions_and_indexes[:-1], functions_and_indexes[1:]
        ):
            out.write(
                f"  {function_labeller(edge_index=edge_index, f_index=idx1, f=f1)} --> {function_labeller(edge_index=edge_index, f_index=idx2, f=f2)}\n"
            )

        f_index_final, f_final = functions_and_indexes[-1]
        for output in edge.outputs:
            out.write(
                f"  {function_labeller(edge_index=edge_index, f_index=f_index_final, f=f_final)} --> {data_node_labeller(data_node=output)}\n"
            )

    out.write("\n")

    out.write("  %% Styling\n")

    colour_calculater = ColorCalculator(colours=colours, alphas=alphas)

    for style_class in StyleClass:
        out.write(f"  classDef {style_class} fill:{colour_calculater[style_class]};\n")
