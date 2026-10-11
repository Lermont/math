"""Additional primary software/protocol sources; run only for source refresh."""
import json
from .fetch_sources import fetch


def main():
    pin = "0a7e36718c5b89dad247e40160726bf782fde804"
    for path in ["README.md", "Project.toml", "src/lps_generators.jl", "src/cayley.jl", "test/pgl_psl_lps.jl"]:
        fetch(f"https://raw.githubusercontent.com/kalmarek/RamanujanGraphs.jl/{pin}/{path}", f"lps-reference/{path}")
    ref = json.loads(fetch("https://api.github.com/repos/libp2p/specs/git/ref/heads/master", "api/libp2p-master-20261011.json"))
    rev = ref["object"]["sha"]
    for name in ["README.md", "gossipsub-v1.0.md", "gossipsub-v1.1.md", "gossipsub-v1.2.md"]:
        fetch(f"https://raw.githubusercontent.com/libp2p/specs/{rev}/pubsub/gossipsub/{name}", f"gossipsub/{name}")
    for name, url in [
        ("networkx-random-regular.html", "https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.random_regular_graph.html"),
        ("networkx-expanders-source.html", "https://networkx.org/documentation/stable/_modules/networkx/generators/expanders.html"),
        ("scipy-eigsh.html", "https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.eigsh.html"),
        ("lps-publisher.html", "https://link.springer.com/article/10.1007/BF02126799"),
        ("external-critique-178.md", "https://gist.githubusercontent.com/Malt7635/4569b09c5ec295f0c1c4b294ee58fa0c/raw/cfca07b29fcc5c89ebedcb5145f07be61f0e7aae/flaw-report-openai-math-family-178.md")
    ]:
        fetch(url, name)


if __name__ == "__main__":
    main()
