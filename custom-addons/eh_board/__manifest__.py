# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
# All implementation work is original. The dashboard engine, chart
# rendering, layout engine and data pipeline are built from the ground
# up in OWL and Python. No layout, naming, markup, or template derives
# from any proprietary or third-party Odoo dashboard module.
#
##############################################################################
{
    "name": "Dashboard Builder",
    "summary": "A live BI workspace for Odoo 17 Community: drag and drop dashboards, "
               "over 20 original SVG chart and widget types computed database side, a world "
               "choropleth map, a pivot and cross-tab matrix, combo charts with a second axis, "
               "cross-model joins and calculated measures without SQL, CSV and Excel file "
               "sources, safe read-only SQL, KPI tiles with targets and trends, gauge charts, "
               "cross-filter and multi-level drill-down, snapshot history, threshold alerts, an "
               "emailed PDF digest, an optional bring-your-own-key AI, ready vertical templates, "
               "presentation and kiosk mode, per-dashboard sharing, and vector PDF, Excel, CSV, "
               "PNG and JSON export - one module, every department, no CDN. "
               "Odoo 17 dashboard, BI dashboard builder, pivot matrix dashboard, geo map "
               "dashboard, cross model dashboard, KPI dashboard with targets, gauge chart, "
               "combo chart, CSV Excel dashboard, vector PDF export, Excel export, dashboard "
               "drilldown, snapshot history dashboard, dashboard alerts, kiosk dashboard, "
               "calculated measures, safe SQL dashboard, BYO key AI dashboard, accessible "
               "dashboard, all in one dashboard suite.",
    "description": """Dashboard Builder is a live business intelligence workspace for Odoo, not a chart arranger. Build a dashboard by dragging tiles onto a snapping grid, group any model's data database side, and click through to the records behind any figure - every number respects your record rules and multi-company access.

The engine is built from the ground up in OWL with original SVG charts, so there is no third party charting bundle to license and nothing loads from an external CDN. Every chart figure is produced with a grouped database read pushed to the database (a KPI tile adds a small trend read), so a board over a million-row ledger opens as fast as one over a handful of records.

This is one module. Everything is included:

- Over 20 original chart, KPI, gauge, table and content item types, plus a pivot / cross-tab matrix with subtotals, a real world choropleth map, and combo charts that draw one measure as bars and another as a line on its own second axis.
- Data from any Odoo model, two models joined on a shared key, an uploaded CSV or Excel file charted by its columns, or a locked-down read-only SQL provider (forced SELECT, keyword whitelist, statement timeout and rollback) with an admin-only credential vault. Calculated (formula) measures without a line of SQL.
- A real drag, resize and compaction grid with per-company layout variants, comfortable / compact density, and a responsive mobile stack.
- A global filter bar with relative-date presets, cross-filter (click any chart to re-scope the whole board) and multi-level drill-down with a breadcrumb.
- Snapshot history so a KPI trends on recorded values, threshold alerts that re-arm on each crossing, an emailed PDF digest, and offline smart insights that read the board in plain language.
- An optional bring-your-own-key AI: it rewrites the board's already-computed insight text into a short narrative using your own OpenAI or Anthropic key, off by default, calling your endpoint directly. Only the computed insight sentences (figures and group labels) are sent, never raw record rows, credentials, SQL or your database name.
- Ready-made vertical dashboards (Contacts, CRM and Sales, Accounting, Warehouse, Point of Sale, HR) that install from a gallery and stay inert until their base app is present, plus save-any-board-as-a-template.
- Per-dashboard sharing and access control, chart palettes, a full-screen presentation and kiosk mode with auto-rotation, a genuine app-level dark and light theme, and vector PDF, Excel, CSV, PNG and JSON export.
- First-class accessibility: keyboard operation and a screen-reader data table behind every chart, a right-to-left aware layout, and an interface translated across nineteen languages.
""",
    "author": "ERP Heritage",
    "website": "https://www.erpheritage.com.au/",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "EUR",
    "category": "Productivity/Dashboard",
    "version": "17.0.5.0.0",
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/eh_board_groups.xml",
        "security/ir.model.access.csv",
        "security/eh_isolation_rules.xml",
        "views/eh_board_datasource_views.xml",
        "views/eh_board_item_views.xml",
        "views/eh_board_dashboard_views.xml",
        "views/eh_board_menus.xml",
        "views/eh_board_alert_views.xml",
        "views/eh_board_credential_views.xml",
        # "views/res_config_settings_views.xml",
        "report/eh_board_report_templates.xml",
        "report/eh_board_reports.xml",
        "data/eh_board_crons.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "eh_board/static/src/**/*",
        ],
        "web.assets_tests": [
            "eh_board/static/tests/**/*",
        ],
    },
    "images": [
        "static/description/banner.gif",
        "static/description/shot_hero.png",
        "static/description/shot_gallery.png",
        "static/description/shot_map.png",
        "static/description/shot_builder.png",
        "static/description/shot_combo.png",
        "static/description/shot_pivot.png",
        "static/description/shot_present.png",
    ],
}
