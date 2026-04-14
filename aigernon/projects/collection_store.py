"""Named collection management for Projects module."""

import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

SYSTEM_COLLECTIONS = {
    "done": "Done",
    "help": "Help",
}


class CollectionStore:
    """Manages named collections within an instance workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.collections_dir = workspace / "collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _collection_dir(self, collection_id: str) -> Path:
        return self.collections_dir / collection_id

    def _collection_path(self, collection_id: str) -> Path:
        return self.collections_dir / collection_id / "collection.yaml"

    def _write_collection(self, data: dict) -> None:
        col_dir = self._collection_dir(data["id"])
        col_dir.mkdir(parents=True, exist_ok=True)
        save = {k: v for k, v in data.items() if k != "id"}
        (col_dir / "collection.yaml").write_text(
            yaml.dump(save, default_flow_style=False)
        )

    # -------------------------------------------------------------------------
    # Bootstrap
    # -------------------------------------------------------------------------

    def bootstrap_system_collections(self) -> None:
        """Create Done and Help collections if they don't exist. Idempotent."""
        for col_id, col_name in SYSTEM_COLLECTIONS.items():
            path = self._collection_path(col_id)
            if not path.exists():
                self._write_collection({
                    "id": col_id,
                    "name": col_name,
                    "system": True,
                    "created_at": datetime.now().isoformat(),
                })

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def get_collection(self, collection_id: str) -> Optional[dict]:
        """Return collection dict (with id injected) or None."""
        path = self._collection_path(collection_id)
        if not path.exists():
            return None
        try:
            data = yaml.safe_load(path.read_text())
        except Exception:
            return None
        if not data:
            return None
        data["id"] = collection_id
        return data

    def list_collections(self) -> dict:
        """Return {'system_collections': [...], 'user_collections': [...]}."""
        system: list[dict] = []
        user: list[dict] = []

        if not self.collections_dir.exists():
            return {"system_collections": [], "user_collections": []}

        for col_dir in sorted(self.collections_dir.iterdir()):
            if not col_dir.is_dir():
                continue
            path = col_dir / "collection.yaml"
            if not path.exists():
                continue
            try:
                data = yaml.safe_load(path.read_text())
            except Exception:
                continue
            if not data:
                continue
            data["id"] = col_dir.name
            if data.get("system"):
                system.append(data)
            else:
                user.append(data)

        # Stable order: done → help → others
        order = {"done": 0, "help": 1}
        system.sort(key=lambda c: order.get(c["id"], 99))
        user.sort(key=lambda c: c.get("created_at", ""))

        return {"system_collections": system, "user_collections": user}

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create_collection(self, name: str) -> str:
        """Create a user collection. Returns the new collection_id (slug)."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "collection"
        base = slug
        counter = 2
        while self._collection_path(slug).exists():
            slug = f"{base}-{counter}"
            counter += 1

        self._write_collection({
            "id": slug,
            "name": name,
            "system": False,
            "created_at": datetime.now().isoformat(),
        })
        return slug

    def rename_collection(self, collection_id: str, new_name: str) -> bool:
        """Rename a user collection. Raises ValueError for system collections."""
        col = self.get_collection(collection_id)
        if not col:
            return False
        if col.get("system"):
            raise ValueError("System collections cannot be renamed")
        col["name"] = new_name
        self._write_collection(col)
        return True

    def delete_collection(self, collection_id: str) -> None:
        """
        Delete a user collection directory.
        Raises ValueError for system collections or if not found.
        Caller is responsible for re-homing projects beforehand.
        """
        col = self.get_collection(collection_id)
        if not col:
            raise ValueError("Collection not found")
        if col.get("system"):
            raise ValueError("System collections cannot be deleted")
        shutil.rmtree(self._collection_dir(collection_id), ignore_errors=True)
