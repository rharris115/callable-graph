from textwrap import fill
from typing import Optional

from graphviz import Digraph

from callable_graph.callable import CallableGraph
from callable_graph.visualisation._visualisation_info import (
    function_str,
    Orientation,
    StyleClass,
    SubgraphInfo,
    ColorCalculator,
    TypeNames,
)


class DataNodeLabeller:
    def __init__(self, graph: CallableGraph):
        self.type_names = TypeNames.from_graph(graph=graph)

    def __call__(self, data_node: str) -> str:
        type_string = self.type_names(data_node=data_node)
        type_string = ": " + type_string if type_string else ""

        return fill(f"{data_node}{type_string}")


def function_id(edge_index: int, f_index: int) -> str:
    return f"f_{edge_index}_{f_index}"


def to_graphviz(
    graph: CallableGraph,
    orientation: Orientation = Orientation.LEFT_TO_RIGHT,
    colours: Optional[dict[StyleClass, str]] = None,
    alphas: Optional[dict[StyleClass, float]] = None,
) -> Digraph:
    subgraph_info = SubgraphInfo.from_graph(graph=graph)

    data_nodel_labeller = DataNodeLabeller(graph=graph)

    colour_calculater = ColorCalculator(colours=colours, alphas=alphas)

    visualisation = Digraph()
    visualisation.graph_attr["rankdir"] = orientation.value

    keywords_visualisation = Digraph()
    intermediate_visualisation = Digraph()
    output_only_visualisation = Digraph()

    # Draw top level nodes.
    for data_node in subgraph_info.top_level_data_nodes:
        style_class = StyleClass.resolve_data_node(data_node=data_node, graph=graph)
        vis = (
            keywords_visualisation
            if style_class == StyleClass.KEYWORD
            else output_only_visualisation
            if style_class == StyleClass.TERMINAL
            else intermediate_visualisation
        )
        vis.node(
            name=data_node,
            label=data_nodel_labeller(data_node=data_node),
            shape="rect",
            style="filled",
            fillcolor=colour_calculater[style_class],
        )

    function_fill_color = colour_calculater[StyleClass.FUNCTION]
    for edge_index, edge in enumerate(graph.edges):
        if edge.subgraph_name is not None:
            continue

        functions_and_indexes = list(enumerate(edge.funcs))

        # Draw the function Nodes
        for f_index, f in functions_and_indexes:
            intermediate_visualisation.node(
                name=function_id(edge_index=edge_index, f_index=f_index),
                label=function_str(function=f),
                shape="ellipse",
                style="filled",
                fillcolor=function_fill_color,
            )

        # Connect inputs with first functions in pipes.
        f_index_start, _ = functions_and_indexes[0]
        for input in edge.inputs:
            intermediate_visualisation.edge(
                head_name=function_id(edge_index=edge_index, f_index=f_index_start),
                tail_name=input,
            )

        # Connect functions in pipes.
        for (idx1, _), (idx2, _) in zip(
            functions_and_indexes[:-1], functions_and_indexes[1:]
        ):
            intermediate_visualisation.edge(
                head_name=function_id(edge_index=edge_index, f_index=idx2),
                tail_name=function_id(edge_index=edge_index, f_index=idx1),
            )

        # Connect last functions with outputs.
        f_index_final, _ = functions_and_indexes[-1]
        for output in edge.outputs:
            intermediate_visualisation.edge(
                head_name=output,
                tail_name=function_id(edge_index=edge_index, f_index=f_index_final),
            )

    # Draw subgraph nodes.
    for subgraph in subgraph_info.subgraphs:
        intermediate_visualisation.node(
            name=subgraph,
            label=subgraph,
            shape="octagon",
            style="filled",
            fillcolor=colour_calculater[StyleClass.SUBGRAPH],
        )

    # Connect subgraph nodes with inputs.
    for subgraph_name, inputs in subgraph_info.subgraph_inputs.items():
        for input in inputs:
            intermediate_visualisation.edge(head_name=subgraph_name, tail_name=input)

    # Connect subgraph nodes with outputs.
    for subgraph_name, outputs in subgraph_info.subgraph_outputs.items():
        for output in outputs:
            intermediate_visualisation.edge(head_name=output, tail_name=subgraph_name)

    # keyword and terminal nodes should be aligned.
    keywords_visualisation.attr(rank="same")
    output_only_visualisation.attr(rank="same")

    visualisation.subgraph(keywords_visualisation)
    visualisation.subgraph(intermediate_visualisation)
    visualisation.subgraph(output_only_visualisation)

    return visualisation
