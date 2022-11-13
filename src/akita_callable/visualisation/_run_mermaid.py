import importlib
from io import TextIOWrapper
from akita_callable.callable import CallableGraphWithTimings
import click

from akita_callable.visualisation._mermaid import (
    Orientation,
    to_mermaid,
)


@click.command()
@click.argument("module_or_graph", type=click.STRING)
@click.argument("out", type=click.File(mode="w"))
@click.option(
    "--orientation",
    type=click.Choice(choices=Orientation, case_sensitive=False),
    default=Orientation.LEFT_TO_RIGHT,
    help="The orientation of the graph.",
)
def main(module_or_graph: str, out: TextIOWrapper, orientation: Orientation):
    """
    Writes the mermaid formatted graph or module of graphs to out.

    MODULE_OR_GRAPH - The graph, graph builder, or module of graphs and graph builders to write. Takes the form
    "module" for an entire module, or "module:graph_or_graph_builder" for an individual graph or graph builder.

    OUT - the stream or file to write to
    """

    tokens = module_or_graph.split(":")

    if len(tokens) == 2:
        module_name, graph_name = tokens
    elif len(tokens) == 1:
        module_name, graph_name = tokens[0], None
    else:
        raise click.exceptions.BadArgumentUsage(f"Can't parse {module_or_graph}")

    module = importlib.import_module(module_name)

    possible_graphs = vars(module)

    if graph_name is not None:
        # If we're focusing on a single graph, evict all the others.
        possible_graphs = {graph_name: possible_graphs.get(graph_name)}

    for possible_graph_name, possible_graph in possible_graphs.items():
        graph = None
        if isinstance(possible_graph, CallableGraphWithTimings):
            graph = possible_graph
        elif isinstance(possible_graph, CallableGraphWithTimings.Builder):
            graph = possible_graph.build()
            possible_graph_name += ".build()"
        if graph is None:
            continue

        out.write(f"# {possible_graph_name}\n")
        out.write("```mermaid\n")
        to_mermaid(graph=graph, out=out, orientation=orientation)
        out.write("```\n\n\n")


if __name__ == "__main__":
    main()
