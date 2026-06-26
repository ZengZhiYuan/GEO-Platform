"""CSV 导出辅助。"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from fastapi.responses import Response

CSV_UTF8_BOM = "\ufeff"


def rows_to_csv_text(headers: list[str], rows: Iterable[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def csv_file_response(*, filename: str, headers: list[str], rows: Iterable[list[Any]]) -> Response:
    content = CSV_UTF8_BOM + rows_to_csv_text(headers, rows)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
