from pathlib import Path

ROOT = Path(__file__).parents[1]
LANGUAGES = ("de", "cs", "en", "es", "fr", "it", "pt")


def test_build_workflow_uses_one_language_and_configured_source() -> None:
    workflow = (ROOT / ".github/workflows/build-release.yml").read_text(
        encoding="utf-8"
    )
    assert 'language:\n        description: "Language release to build"' in workflow
    assert all(f"          - {language}" in workflow for language in LANGUAGES)
    inputs = workflow.split("permissions:", 1)[0]
    assert "      source_url:" not in inputs
    assert "      source_label:" not in inputs
    assert "      languages:" not in inputs
    assert 'language=os.environ["REQUESTED_LANGUAGE"]' in workflow
    assert "source = config.source_for(language)" in workflow
    assert '--language "$LANGUAGE"' in workflow
    assert "data-${{ inputs.language }}-${{ inputs.dataset_version }}" in workflow


def test_publish_workflow_verifies_and_publishes_one_language() -> None:
    workflow = (ROOT / ".github/workflows/publish-release.yml").read_text(
        encoding="utf-8"
    )

    assert 'language:\n        description: "Language release to publish"' in workflow
    assert all(f"          - {language}" in workflow for language in LANGUAGES)
    assert '--expected-language "$LANGUAGE"' in workflow
    assert "data-${{ inputs.language }}-${{ inputs.dataset_version }}" in workflow
    assert "without rebuilding" in workflow


def test_batch_workflow_captures_one_builder_commit_and_syncs_once() -> None:
    workflow = (ROOT / ".github/workflows/release-selected.yml").read_text(
        encoding="utf-8"
    )
    assert 'default: "de,en,es"' in workflow
    assert "builder_commit={os.environ['GITHUB_SHA']}" in workflow
    assert (
        'matrix = {"include": [{"language": language} for language in languages]}'
        in workflow
    )
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in workflow
    assert (
        "lexhint-datasets-${{ matrix.language }}-${{ inputs.dataset_version }}-${{ needs.plan.outputs.builder_commit }}"
        in workflow
    )
    assert '--target "$BUILDER_COMMIT"' in workflow
    assert "TAG: data-${{ matrix.language }}-${{ inputs.dataset_version }}" in workflow
    assert "needs: [plan, publish-all]" in workflow
    assert workflow.index("publish-all:") < workflow.index("sync-catalog:")
    assert workflow.count('git commit -m "chore: synchronize dataset catalog"') == 1
    assert "group: lexhint-datasets-catalog" in workflow


def test_catalog_refresh_workflow_is_serialized_and_non_force_pushing() -> None:
    workflow = (ROOT / ".github/workflows/refresh-catalog.yml").read_text(
        encoding="utf-8"
    )
    assert "name: Refresh dataset catalog" in workflow
    assert "group: lexhint-datasets-catalog" in workflow
    assert "--release-tag" in workflow
    assert "git pull --rebase origin main" in workflow
    assert "git push origin HEAD:main" in workflow
    assert "--force" not in workflow
