# core/engine/graph_planner.py
"""Spark Graph-Based Memory Planner.

Represents inference execution as a dependency graph. Groups model layers and MoE
experts into topological execution clusters to plan grouped memory movements,
reducing sequential SSD seek/read latency overheads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

logger = logging.getLogger("spark.engine.graph_planner")


@dataclass
class ExecutionCluster:
    """A cluster of model tensors that execute together in the model graph."""
    cluster_id: str
    block_ids: List[str] = field(default_factory=list)
    total_bytes: int = 0
    dependencies: List[str] = field(default_factory=list) # IDs of clusters that must execute before this one


class GraphMemoryPlanner:
    """Topologically plans grouped weight movement over execution clusters.

    Instead of streaming tensors one-by-one, the graph planner groups related
    attention keys/queries, linear projections, or routing experts into a single
    coherent cluster, optimization storage latency.
    """

    def __init__(self):
        self._clusters: Dict[str, ExecutionCluster] = {}
        self._graph: Dict[str, List[str]] = {}

    def build_execution_graph(self, layer_count: int, expert_count: int = -1) -> None:
        """Construct the execution graph topology for the model."""
        self._clusters.clear()
        self._graph.clear()

        # Build clusters for each layer
        for i in range(layer_count):
            # Attention cluster
            attn_id = f"layer.{i}.attention"
            self._clusters[attn_id] = ExecutionCluster(
                cluster_id=attn_id,
                block_ids=[
                    f"layer.{i}.self_attn.q_proj",
                    f"layer.{i}.self_attn.k_proj",
                    f"layer.{i}.self_attn.v_proj",
                    f"layer.{i}.self_attn.o_proj"
                ]
            )

            # MLP/Expert clusters
            if expert_count > 0:
                for e in range(expert_count):
                    exp_id = f"layer.{i}.expert.{e}"
                    self._clusters[exp_id] = ExecutionCluster(
                        cluster_id=exp_id,
                        block_ids=[
                            f"layer.{i}.expert.{e}.gate_proj",
                            f"layer.{i}.expert.{e}.up_proj",
                            f"layer.{i}.expert.{e}.down_proj"
                        ],
                        dependencies=[attn_id]
                    )
            else:
                mlp_id = f"layer.{i}.mlp"
                self._clusters[mlp_id] = ExecutionCluster(
                    cluster_id=mlp_id,
                    block_ids=[
                        f"layer.{i}.mlp.gate_proj",
                        f"layer.{i}.mlp.up_proj",
                        f"layer.{i}.mlp.down_proj"
                    ],
                    dependencies=[attn_id]
                )

            # Link sequential layer dependencies
            if i > 0:
                prev_mlp = f"layer.{i-1}.mlp" if expert_count <= 0 else [f"layer.{i-1}.expert.{e}" for e in range(expert_count)]
                if isinstance(prev_mlp, str):
                    self._clusters[attn_id].dependencies.append(prev_mlp)
                else:
                    self._clusters[attn_id].dependencies.extend(prev_mlp)

        logger.info("Graph Planner: Compiled execution graph with %d clusters.", len(self._clusters))

    def get_cluster_sequence(self) -> List[str]:
        """Perform a topological sort to get the optimal loading sequence of clusters."""
        visited: Set[str] = set()
        stack: List[str] = []

        def dfs(node: str):
            visited.add(node)
            cluster = self._clusters.get(node)
            if cluster:
                for dep in cluster.dependencies:
                    if dep not in visited:
                        dfs(dep)
            stack.append(node)

        for cid in self._clusters:
            if cid not in visited:
                dfs(cid)

        # Return reversed stack for topological order
        return stack[::-1]

    def optimize_movement(self, sequence: List[str]) -> List[str]:
        """Flatten a topological cluster sequence into raw block loading IDs."""
        flat_blocks = []
        for cid in sequence:
            cluster = self._clusters.get(cid)
            if cluster:
                flat_blocks.extend(cluster.block_ids)
        return flat_blocks
