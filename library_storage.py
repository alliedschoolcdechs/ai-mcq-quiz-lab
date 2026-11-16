import hashlib
from pathlib import Path
from threading import Lock


_LIBRARY_WRITE_LOCK = Lock()


class DuplicateLibraryFileError(ValueError):
    def __init__(self, existing_name):
        self.existing_name = existing_name
        super().__init__(f"This file already exists in the library as {existing_name}.")


def add_library_file(library_dir, file_name, content, supported_extensions):
    library_dir = Path(library_dir)
    safe_name = Path(file_name).name
    extension = Path(safe_name).suffix.casefold()
    allowed_extensions = {
        item.casefold() for item in supported_extensions
    }
    if not safe_name or extension not in allowed_extensions:
        raise ValueError("This file type cannot be added to the library.")

    content_hash = hashlib.sha256(content).digest()
    with _LIBRARY_WRITE_LOCK:
        for existing_path in sorted(
            library_dir.iterdir(),
            key=lambda path: path.name.casefold(),
        ):
            if (
                not existing_path.is_file()
                or existing_path.suffix.casefold() not in allowed_extensions
                or existing_path.stat().st_size != len(content)
            ):
                continue
            existing_hash = hashlib.sha256()
            with existing_path.open("rb") as existing_file:
                for chunk in iter(lambda: existing_file.read(1024 * 1024), b""):
                    existing_hash.update(chunk)
            if existing_hash.digest() == content_hash:
                raise DuplicateLibraryFileError(existing_path.name)

        original_path = library_dir / safe_name
        destination = original_path
        version = 2
        while destination.exists():
            destination = library_dir / (
                f"{original_path.stem} ({version}){original_path.suffix}"
            )
            version += 1

        with destination.open("xb") as destination_file:
            destination_file.write(content)
        return destination
