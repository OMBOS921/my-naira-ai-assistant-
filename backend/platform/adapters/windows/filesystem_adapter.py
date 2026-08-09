import os
import shutil
import asyncio
from pathlib import Path
from typing import List

from backend.platform.ports.filesystem_port import FilesystemPort
from backend.modules.pc_control._types import FileEntry, FileOpResult

def _resolve_path(path: str) -> Path:
    return Path(path).resolve()

def _validate_path_chars(path: Path) -> str | None:
    # Basic validation for windows
    invalid_chars = '<>"|?*'
    if any(c in str(path) for c in invalid_chars):
        return f"Path contains invalid characters: {invalid_chars}"
    return None

class WindowsFilesystemAdapter(FilesystemPort):
    async def filesystem_list_directory(self, path: str) -> List[FileEntry]:
        def _list() -> List[FileEntry]:
            p = _resolve_path(path)
            if not p.exists() or not p.is_dir():
                raise RuntimeError(f"Path does not exist or is not a directory: {path}")
            entries = []
            for child in sorted(p.iterdir(), key=lambda x: x.name):
                try:
                    stat = child.stat()
                    entries.append(
                        FileEntry(
                            name=child.name,
                            path=str(child.resolve()),
                            is_directory=child.is_dir(),
                            size_bytes=stat.st_size if child.is_file() else 0,
                            modified_at=stat.st_mtime,
                        )
                    )
                except OSError:
                    continue
            return entries
        return await asyncio.to_thread(_list)

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        def _read() -> str:
            p = _resolve_path(path)
            if not p.exists() or not p.is_file():
                raise RuntimeError(f"File does not exist: {path}")
            return p.read_text(encoding=encoding)
        return await asyncio.to_thread(_read)

    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        def _write() -> FileOpResult:
            p = _resolve_path(path)
            invalid_char = _validate_path_chars(p)
            if invalid_char:
                return FileOpResult(success=False, path=str(p), error=invalid_char)
            if not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            try:
                p.write_text(content, encoding=encoding)
                return FileOpResult(success=True, path=str(p))
            except Exception as exc:
                return FileOpResult(success=False, path=str(p), error=str(exc))
        return await asyncio.to_thread(_write)

    async def filesystem_delete_file(self, path: str) -> None:
        def _delete() -> None:
            p = _resolve_path(path)
            if p.exists() and p.is_file():
                p.unlink()
        await asyncio.to_thread(_delete)

    async def filesystem_create_directory(self, path: str) -> FileOpResult:
        def _mkdir() -> FileOpResult:
            p = _resolve_path(path)
            try:
                p.mkdir(parents=True, exist_ok=True)
                return FileOpResult(success=True, path=str(p))
            except Exception as exc:
                return FileOpResult(success=False, path=str(p), error=str(exc))
        return await asyncio.to_thread(_mkdir)

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        def _rmdir() -> None:
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return
            if recursive:
                shutil.rmtree(str(p))
            else:
                p.rmdir()
        await asyncio.to_thread(_rmdir)

    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> FileOpResult:
        def _zip() -> FileOpResult:
            try:
                # shutil.make_archive adds .zip, so we need to strip it if provided
                base = str(Path(output_zip_path).with_suffix(''))
                shutil.make_archive(base, 'zip', source_dir)
                return FileOpResult(success=True, path=output_zip_path)
            except Exception as exc:
                return FileOpResult(success=False, path=output_zip_path, error=str(exc))
        return await asyncio.to_thread(_zip)

    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> FileOpResult:
        def _extract() -> FileOpResult:
            try:
                shutil.unpack_archive(zip_path, extract_to_dir)
                return FileOpResult(success=True, path=extract_to_dir)
            except Exception as exc:
                return FileOpResult(success=False, path=extract_to_dir, error=str(exc))
        return await asyncio.to_thread(_extract)

    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> FileOpResult:
        def _copy() -> FileOpResult:
            try:
                src = Path(source_path)
                if src.is_dir():
                    shutil.copytree(source_path, dest_path)
                else:
                    shutil.copy2(source_path, dest_path)
                return FileOpResult(success=True, path=dest_path)
            except Exception as exc:
                return FileOpResult(success=False, path=dest_path, error=str(exc))
        return await asyncio.to_thread(_copy)

    async def filesystem_move_item(self, source_path: str, dest_path: str) -> FileOpResult:
        def _move() -> FileOpResult:
            try:
                shutil.move(source_path, dest_path)
                return FileOpResult(success=True, path=dest_path)
            except Exception as exc:
                return FileOpResult(success=False, path=dest_path, error=str(exc))
        return await asyncio.to_thread(_move)
