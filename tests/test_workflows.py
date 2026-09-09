from pathlib import Path

from scripts.config import SUPPORTED_BASE_LANGUAGES

ROOT = Path(__file__).parents[1]
LANGUAGES = SUPPORTED_BASE_LANGUAGES


def test_build_workflow_uses_one_language_and_source_variant() -> None:
    workflow = (ROOT / ".github/workflows/build-release.yml").read_text(
        encoding="utf-8"
    )
    assert 'language:\n        description: "Language release to build"' in workflow
    assert all(f"          - {language}" in workflow for language in LANGUAGES)
    inputs = workflow.split("permissions:", 1)[0]
    assert "      source_url:" not in inputs
    assert "      source_label:" not in inputs
    assert "      languages:" not in inputs
    assert "source_variant:" in workflow
    assert '--source-variant "$SOURCE_VARIANT"' in workflow
    assert (
        "data-${{ inputs.language }}-${{ inputs.source_variant }}-${{ inputs.dataset_version }}"
        in workflow
    )
    assert "--expected-version 0.4.6" in workflow


def test_publish_workflow_verifies_and_publishes_one_language() -> None:
    workflow = (ROOT / ".github/workflows/publish-release.yml").read_text(
        encoding="utf-8"
    )
    assert 'language:\n        description: "Language release to publish"' in workflow
    assert all(f"          - {language}" in workflow for language in LANGUAGES)
    assert '--expected-language "${{ inputs.language }}"' in workflow
    assert '--expected-source-variant "${{ inputs.source_variant }}"' in workflow
    assert (
        "data-${{ inputs.language }}-${{ inputs.source_variant }}-${{ inputs.dataset_version }}"
        in workflow
    )
    assert "never reacquires source bytes" not in workflow
    assert "exact source-qualified candidate" in workflow


def test_batch_workflow_captures_source_qualified_matrix_and_syncs_once() -> None:
    workflow = (ROOT / ".github/workflows/release-selected.yml").read_text(
        encoding="utf-8"
    )
    assert 'default: "de,en,es"' in workflow
    assert "source_variant:" in workflow
    assert "repository: buchwandler/lexhint" in workflow
    assert "ref: ${{ inputs.lexhint_ref }}" in workflow
    assert (
        'matrix = {"include": [{"language": language, "source_variant": os.environ["SOURCE_VARIANT"]}'
        in workflow
    )
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in workflow
    assert (
        "lexhint-datasets-${{ matrix.language }}-${{ matrix.source_variant }}"
        in workflow
    )
    assert (
        "TAG: data-${{ matrix.language }}-${{ matrix.source_variant }}-${{ inputs.dataset_version }}"
        in workflow
    )
    assert "needs: publish-all" in workflow
    assert workflow.index("publish-all:") < workflow.index("sync-catalog:")
    assert "catalog/datasets-v2.json" in workflow


def test_catalog_refresh_workflow_is_serialized_and_non_force_pushing() -> None:
    workflow = (ROOT / ".github/workflows/refresh-catalog.yml").read_text(
        encoding="utf-8"
    )
    assert "name: Refresh dataset catalog" in workflow
    assert "group: lexhint-datasets-catalog-v2" in workflow
    assert "--release-tag" in workflow
    assert "catalog/datasets-v2.json" in workflow
    assert "git pull --rebase origin main" in workflow
    assert "git push origin HEAD:main" in workflow
    assert "--force" not in workflow
