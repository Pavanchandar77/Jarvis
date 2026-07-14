# core/pipeline/planner.py
"""Spark Pipeline Task Planner.

Transforms user prompts into a Directed Acyclic Graph (DAG) of individual execution
tasks, optimizing parallel execution pathways.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

logger = logging.getLogger("spark.pipeline.planner")


@dataclass
class TaskNode:
    """A single node in the task execution graph."""
    task_id: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"          # pending | running | completed | failed
    output: Optional[str] = None


class TaskPlanner:
    """Constructs a Directed Acyclic Graph (DAG) of task steps for complex requests."""

    def build_dag(self, query: str, intent: str, complexity: float) -> List[TaskNode]:
        """Convert a user query into a structured set of dependent task nodes."""
        logger.info("Pipeline Task Planner: Building DAG for intent '%s'...", intent)
        dag: List[TaskNode] = []

        if complexity < 0.3:
            # Simple request: single step
            dag.append(TaskNode(
                task_id="generate_response",
                description=f"Process request directly: {query[:60]}..."
            ))
            return dag

        # Multi-stage task mappings
        if intent == "coding":
            dag.append(TaskNode(task_id="gather_requirements", description="Define software requirements and inputs."))
            dag.append(TaskNode(task_id="design_architecture", description="Define module architecture and API specifications.", dependencies=["gather_requirements"]))
            dag.append(TaskNode(task_id="create_database_schema", description="Create database tables/schemas if needed.", dependencies=["design_architecture"]))
            dag.append(TaskNode(task_id="write_backend_code", description="Implement backend APIs and models.", dependencies=["design_architecture", "create_database_schema"]))
            dag.append(TaskNode(task_id="write_frontend_code", description="Implement frontend user interface.", dependencies=["design_architecture"]))
            dag.append(TaskNode(task_id="verify_integration", description="Run code validations and integration check.", dependencies=["write_backend_code", "write_frontend_code"]))
        
        elif intent == "research":
            dag.append(TaskNode(task_id="literature_search", description="Search database for matching research preprints."))
            dag.append(TaskNode(task_id="extract_key_findings", description="Summarize results from downloaded PDFs.", dependencies=["literature_search"]))
            dag.append(TaskNode(task_id="synthesize_report", description="Write research report.", dependencies=["extract_key_findings"]))

        elif intent == "reasoning":
            dag.append(TaskNode(task_id="decompose_query", description="Break question into logical sub-premises."))
            dag.append(TaskNode(task_id="verify_each_premise", description="Evaluate validation metrics on each premise.", dependencies=["decompose_query"]))
            dag.append(TaskNode(task_id="compile_final_argument", description="Synthesize logical conclusions.", dependencies=["verify_each_premise"]))

        else:
            # General complex request
            dag.append(TaskNode(task_id="draft_initial_response", description="Create initial draft."))
            dag.append(TaskNode(task_id="second_pass_refine", description="Polish style and correct factual inconsistencies.", dependencies=["draft_initial_response"]))

        return dag

    def get_ready_tasks(self, dag: List[TaskNode]) -> List[TaskNode]:
        """Return task nodes whose dependencies are all completed."""
        completed_ids = {node.task_id for node in dag if node.status == "completed"}
        ready = []
        for node in dag:
            if node.status == "pending":
                # Check if all dependencies are satisfied
                if all(dep in completed_ids for dep in node.dependencies):
                    ready.append(node)
        return ready
