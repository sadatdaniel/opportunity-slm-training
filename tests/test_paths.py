"""Path sanity: pipeline modules must anchor to the repo root, not a parent.

Regression test for an off-by-one PROJECT_ROOT bug that silently wrote
collected data outside the repository.
"""

import project.collect
import project.dedupe
import project.normalize
from project.sources import inventory, registry
from training.common import experiment as training_experiment


def test_project_roots_are_repo_root():
    expected = registry.PROJECT_ROOT
    assert expected.name == "llm_training_project"
    assert project.collect.PROJECT_ROOT == expected
    assert project.normalize.PROJECT_ROOT == expected
    assert project.dedupe.PROJECT_ROOT == expected
    assert inventory.PROJECT_ROOT == expected
    assert training_experiment.PROJECT_ROOT == expected
    assert (expected / "sources" / "registry.yaml").exists()
    assert (expected / "training" / "classifier" / "config.yaml").exists()
