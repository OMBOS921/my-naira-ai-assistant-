from abc import ABC, abstractmethod
from typing import List
from backend.modules.pc_control._types import FileEntry, FileOpResult

class FilesystemPort(ABC):
    @abstractmethod
    async def filesystem_list_directory(self, path: str) -> List[FileEntry]:
        pass

    @abstractmethod
    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        pass

    @abstractmethod
    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        pass

    @abstractmethod
    async def filesystem_delete_file(self, path: str) -> None:
        pass

    @abstractmethod
    async def filesystem_create_directory(self, path: str) -> FileOpResult:
        pass

    @abstractmethod
    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        pass

    @abstractmethod
    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> FileOpResult:
        pass

    @abstractmethod
    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> FileOpResult:
        pass

    @abstractmethod
    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> FileOpResult:
        pass

    @abstractmethod
    async def filesystem_move_item(self, source_path: str, dest_path: str) -> FileOpResult:
        pass
