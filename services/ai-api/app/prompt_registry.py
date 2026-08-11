import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class PromptAsset:
    name: str
    version: str
    text: str
    digest: str


class PromptRegistry:
    """Load versioned prompts and fail closed if a checked-in file drifts."""

    def __init__(self, directory: Path) -> None:
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported prompt manifest schema")
        self._assets: dict[str, PromptAsset] = {}
        for name, metadata in manifest.get("prompts", {}).items():
            path = (directory / metadata["file"]).resolve()
            if path.parent != directory.resolve():
                raise ValueError("Prompt files must remain inside prompt directory")
            raw = path.read_bytes()
            digest = sha256(raw).hexdigest()
            if digest != metadata["sha256"]:
                raise ValueError(f"Prompt checksum mismatch: {name}")
            self._assets[name] = PromptAsset(
                name=name,
                version=metadata["version"],
                text=raw.decode("utf-8").strip(),
                digest=digest,
            )
        if set(self._assets) != {"planner", "composer"}:
            raise ValueError("Prompt manifest must define planner and composer")

    def get(self, name: str) -> PromptAsset:
        return self._assets[name]

    @property
    def versions(self) -> dict[str, str]:
        return {name: asset.version for name, asset in self._assets.items()}
