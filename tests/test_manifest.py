from skillhub.manifest import load_manifest


def test_example_manifest_loads() -> None:
    manifest = load_manifest("examples/hello-skill/skillhub.yaml")
    assert manifest.versioned_key == "nexi-lab/hello-skill@0.1.0"
    assert manifest.files.skill_doc == "SKILL.md"
