from io import BytesIO

import pytest
from fastapi import UploadFile

from app.api.routes import normalize_upload_files
from shared.responses import validation_errors_safe

pytestmark = pytest.mark.anyio


async def test_normalize_upload_files_accepts_none() -> None:
    assert normalize_upload_files(None) == []


async def test_normalize_upload_files_accepts_single_file() -> None:
    file = UploadFile(file=BytesIO(), filename="case.md")

    assert normalize_upload_files(file) == [file]


async def test_normalize_upload_files_accepts_file_list() -> None:
    files = [
        UploadFile(file=BytesIO(), filename="case.md"),
        UploadFile(file=BytesIO(), filename="rates.xlsx"),
    ]

    assert normalize_upload_files(files) == files


async def test_validation_errors_safe_serializes_upload_file_input() -> None:
    file = UploadFile(file=BytesIO(), filename="case.md")

    errors = [
        {
            "type": "list_type",
            "loc": ("body", "files"),
            "msg": "Input should be a valid list",
            "input": file,
        }
    ]

    assert validation_errors_safe(errors) == [
        {
            "type": "list_type",
            "loc": ("body", "files"),
            "msg": "Input should be a valid list",
            "input": str(file),
        }
    ]
