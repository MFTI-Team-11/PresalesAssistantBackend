from io import BytesIO

from fastapi import UploadFile

from app.routes import normalize_upload_files


def test_normalize_upload_files_accepts_none() -> None:
    assert normalize_upload_files(None) == []


def test_normalize_upload_files_accepts_single_file() -> None:
    file = UploadFile(file=BytesIO(), filename="case.md")

    assert normalize_upload_files(file) == [file]


def test_normalize_upload_files_accepts_file_list() -> None:
    files = [
        UploadFile(file=BytesIO(), filename="case.md"),
        UploadFile(file=BytesIO(), filename="rates.xlsx"),
    ]

    assert normalize_upload_files(files) == files
