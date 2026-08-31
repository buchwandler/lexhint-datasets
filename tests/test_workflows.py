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
