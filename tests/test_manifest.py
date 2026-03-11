from skillhub.manifest import load_manifest
from skillhub.local_package import load_local_package


def test_example_manifest_loads() -> None:
    manifest = load_manifest("examples/hello-skill/skillhub.yaml")
    assert manifest.versioned_key == "nexi-lab/hello-skill@0.1.0"
    assert manifest.files.skill_doc == "SKILL.md"


def test_local_package_loads_with_file_artifact() -> None:
    package = load_local_package("examples/hello-skill")
    assert package.manifest.versioned_key == "nexi-lab/hello-skill@0.1.0"
    assert package.artifact_uri.startswith("file://")
    assert package.artifact_digest.startswith("sha256:")
