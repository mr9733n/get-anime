# make_bin/version.py
"""
Создание Windows Version Resource для PyInstaller.
Совместимость с PyInstaller 6.x (где убрали Version).
"""
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo,
    FixedFileInfo,
    StringFileInfo,
    StringTable,
    StringStruct,
    VarFileInfo,
    VarStruct
)


def create_version_resource(
        file_version: str,
        product_version: str,
        company_name: str,
        file_description: str,
        internal_name: str,
        legal_copyright: str,
        original_filename: str,
        product_name: str
) -> VSVersionInfo:
    """
    Создаёт VSVersionInfo для Windows executable.

    Args:
        file_version: Версия файла (например, "0.3.8.37")
        product_version: Версия продукта (например, "0.3.8")
        company_name: Название компании
        file_description: Описание файла
        internal_name: Внутреннее имя
        legal_copyright: Копирайт
        original_filename: Оригинальное имя файла
        product_name: Название продукта

    Returns:
        VSVersionInfo object
    """

    def _tuple4(v: str) -> tuple[int, int, int, int]:
        parts = [int(p) for p in str(v).split('.') if p.isdigit()]
        parts = (parts + [0, 0, 0, 0])[:4]
        return tuple(parts)

    filevers = _tuple4(file_version)
    prodvers = _tuple4(product_version)

    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=filevers,
            prodvers=prodvers,
            mask=0x3f,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', company_name),
                    StringStruct('FileDescription', file_description),
                    StringStruct('FileVersion', str(file_version)),
                    StringStruct('InternalName', internal_name),
                    StringStruct('LegalCopyright', legal_copyright),
                    StringStruct('OriginalFilename', original_filename),
                    StringStruct('ProductName', product_name),
                    StringStruct('ProductVersion', str(product_version)),
                ])
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ]
    )


def version_from_dict(version_info: dict) -> VSVersionInfo:
    """
    Создаёт VSVersionInfo из словаря.

    Args:
        version_info: Словарь с ключами:
            - FileVersion
            - ProductVersion
            - CompanyName
            - FileDescription
            - InternalName
            - LegalCopyright
            - OriginalFilename
            - ProductName

    Returns:
        VSVersionInfo object
    """
    return create_version_resource(
        file_version=version_info["FileVersion"],
        product_version=version_info["ProductVersion"],
        company_name=version_info["CompanyName"],
        file_description=version_info["FileDescription"],
        internal_name=version_info["InternalName"],
        legal_copyright=version_info["LegalCopyright"],
        original_filename=version_info["OriginalFilename"],
        product_name=version_info["ProductName"],
    )