# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""HTTP endpoints for server-side exports.

The Excel export is real: a workbook with a sheet per widget (headers +
grouped rows, or a single value for a KPI), built from the same payloads the
board renders - so the numbers match to the cell. No screenshot rasterising.
"""
import io
import json

from odoo import http
from odoo.http import request, content_disposition


class EhBoardController(http.Controller):

    @http.route("/eh_board/export/xlsx", type="http", auth="user")
    def export_xlsx(self, dashboard_id=None, item_id=None, options="{}", **kw):
        try:
            import xlsxwriter
        except ImportError:
            return request.not_found()
        # A missing or non-numeric id must be a clean 404, not an uncaught
        # int(None)/int("x") -> HTTP 500.
        try:
            did = int(dashboard_id)
        except (TypeError, ValueError):
            return request.not_found()
        dashboard = request.env["eh.board.dashboard"].browse(did)
        if not dashboard.exists():
            return request.not_found()
        try:
            opts = json.loads(options or "{}")
        except (ValueError, TypeError):
            opts = {}
        data = dashboard.get_data(opts)

        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {"in_memory": True})
        f_title = book.add_format({"bold": True, "font_size": 13, "font_color": "#14181a"})
        f_head = book.add_format({"bold": True, "bg_color": "#eef1f2", "border": 1})
        f_num = book.add_format({"num_format": "#,##0.###", "border": 1})
        f_pct = book.add_format({"num_format": "0.0%", "border": 1})
        f_txt = book.add_format({"border": 1})

        meta_by_id = {m["id"]: m for m in data.get("item_meta", [])}
        used_names = set()
        for payload in data.get("items", []):
            meta = meta_by_id.get(payload.get("id"), {})
            title = (meta.get("title") or payload.get("type") or "Widget")
            name = self._safe_sheet(title, used_names)
            sheet = book.add_worksheet(name)
            sheet.set_column(0, 0, 32)
            sheet.write(0, 0, title, f_title)
            if payload.get("category") == "kpi":
                sheet.write(2, 0, "Value", f_head)
                sheet.write(2, 1, payload.get("value", 0), f_num)
            elif payload.get("category") == "content":
                continue
            else:
                table = dashboard._payload_table(payload)
                for c, column in enumerate(table.get("columns", [])):
                    sheet.set_column(c, c, 32 if c == 0 else 16)
                    sheet.write(2, c, str(column.get("label") or "Value"), f_head)
                for r, row in enumerate(table.get("rows", [])):
                    for c, value in enumerate(row):
                        column = table["columns"][c]
                        if column.get("percentage"):
                            sheet.write_number(3 + r, c, float(value or 0), f_pct)
                        elif column.get("numeric") and not isinstance(value, bool):
                            sheet.write_number(3 + r, c, float(value or 0), f_num)
                        else:
                            sheet.write(3 + r, c,
                                        "" if value is None else str(value), f_txt)

        if not book.worksheets():
            book.add_worksheet("Dashboard").write(0, 0, data.get("name", "Dashboard"))
        book.close()
        content = stream.getvalue()
        filename = "%s.xlsx" % (data.get("name") or "dashboard")
        return request.make_response(content, headers=[
            ("Content-Type",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", content_disposition(filename)),
            ("Content-Length", len(content)),
        ])

    def _safe_sheet(self, name, used):
        clean = "".join(c for c in name if c not in "[]:*?/\\")[:28] or "Sheet"
        # xlsxwriter dedups sheet names case-INSENSITIVELY and raises
        # DuplicateWorksheetName (a 500) on a collision. Track the lower-cased
        # name so two widgets differing only in case get distinct sheets.
        base, i = clean, 1
        while clean.lower() in used:
            i += 1
            clean = "%s %d" % (base[:25], i)
        used.add(clean.lower())
        return clean
