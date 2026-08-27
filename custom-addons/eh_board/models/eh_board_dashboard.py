# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
import ast
import logging

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EhBoardDashboard(models.Model):
    _name = "eh.board.dashboard"
    _description = "Dashboard"
    _order = "sequence, name"

    name = fields.Char(required=True, default="New Dashboard")
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        default="draft", required=True)
    owner_id = fields.Many2one(
        "res.users", string="Owner", default=lambda self: self.env.user)
    company_ids = fields.Many2many(
        "res.company", string="Companies",
        default=lambda self: self.env.company)
    group_ids = fields.Many2many(
        "res.groups", string="Restricted to groups",
        help="Leave empty to let every internal user with dashboard access see it.")
    shared_user_ids = fields.Many2many(
        "res.users", "eh_board_dashboard_shared_user_rel", "dashboard_id", "user_id",
        string="Shared with",
        help="Specific users who may open this dashboard even while it is a draft.")
    description = fields.Text()
    thumbnail = fields.Binary(attachment=True)
    is_template = fields.Boolean()

    refresh_mode = fields.Selection(
        [("off", "Manual"), ("interval", "Auto (interval)"), ("live", "Live")],
        default="off", required=True)
    refresh_interval = fields.Integer(
        default=60, help="Seconds between refreshes when auto-refresh is on.")
    is_kiosk = fields.Boolean(string="Kiosk-ready")
    palette = fields.Selection(
        [("default", "Heritage"), ("ocean", "Ocean"), ("sunset", "Sunset"),
         ("forest", "Forest"), ("mono", "Monochrome")],
        default="default", help="Chart colour palette for this dashboard.")
    default_date_preset = fields.Selection(
        [("all", "None"), ("today", "Today"), ("this_week", "This week"),
         ("this_month", "This month"), ("this_quarter", "This quarter"),
         ("this_year", "This year"), ("wtd", "Week to date"), ("mtd", "Month to date"),
         ("qtd", "Quarter to date"), ("ytd", "Year to date"), ("last_month", "Last month"),
         ("last_7", "Last 7 days"), ("last_30", "Last 30 days"), ("last_90", "Last 90 days")],
        default="all",
        help="The date range this dashboard opens with (the board date filter's start value).")
    digest_enabled = fields.Boolean(
        string="Email digest", help="Email this dashboard as a PDF on a schedule.")
    digest_user_ids = fields.Many2many(
        "res.users", "eh_board_dashboard_digest_user_rel", "dashboard_id", "user_id",
        string="Digest recipients")

    item_ids = fields.One2many("eh.board.item", "dashboard_id", string="Items")
    item_count = fields.Integer(compute="_compute_item_count")
    layout_version_ids = fields.One2many(
        "eh.board.layout.version", "dashboard_id", string="Layouts")
    active_layout_id = fields.Many2one(
        "eh.board.layout.version", string="Active layout",
        # Do NOT carry the pointer to the ORIGINAL board's layout on copy(); the
        # duplicate resolves its own active layout from its copied layout list.
        copy=False)
    filter_ids = fields.One2many(
        "eh.board.filter", "dashboard_id", string="Filters")

    @api.depends("item_ids")
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    # ------------------------------------------------------------------ data
    def _active_layout(self):
        self.ensure_one()
        if self.active_layout_id:
            return self.active_layout_id
        company = self.env.company
        match = self.layout_version_ids.filtered(
            lambda l: l.is_active and (not l.company_id or l.company_id == company))
        return match[:1] or self.layout_version_ids[:1]

    _LAZY_EAGER = 8   # widgets rendered with data up front; the rest lazy-load

    def get_data(self, options=None, lazy=False):
        """Full payload for the OWL board: config, items, layout, filters.

        With ``lazy`` on, only the first widgets carry data; the rest are listed
        in ``lazy_ids`` and fetched by the client as they scroll into view, so a
        20-30 widget board paints the visible ones first."""
        self.ensure_one()
        options = options or {}
        layout = self._active_layout()
        items, lazy_ids = [], []
        for i, item in enumerate(self.item_ids):
            if lazy and i >= self._LAZY_EAGER:
                lazy_ids.append(item.id)
            else:
                items.append(item.get_payload(options))
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "refresh_mode": self.refresh_mode,
            "refresh_interval": self.refresh_interval,
            "is_kiosk": self.is_kiosk,
            "palette": self.palette or "default",
            "default_date_preset": self.default_date_preset or "all",
            "can_edit": self._can_edit(),
            "layout": layout.grid if layout else {},
            "density": layout.density if layout else "comfortable",
            "filters": [f.spec() for f in self.filter_ids],
            "items": items,
            "lazy_ids": lazy_ids,
            "item_meta": [item._meta() for item in self.item_ids],
        }

    def list_boards(self):
        """Boards the current user may open (record-rule filtered) for the
        in-app dashboard switcher."""
        return [{"id": b.id, "name": b.name}
                for b in self.search([], order="name")]

    @api.model
    def count_domain_matches(self, model_name, domain, include_archived=False):
        """Safe live match-count for the builder's compact domain editor.

        The domain literal is parsed with ``ast.literal_eval`` (never evaluated as
        code) and counted AS THE CURRENT USER, so record rules apply and a value
        containing an apostrophe no longer breaks a client-side quote-swap parse.
        Returns None when the domain is unparseable or the model is unknown."""
        if not model_name or model_name not in self.env:
            return None
        try:
            parsed = ast.literal_eval(domain or "[]")
        except (ValueError, SyntaxError):
            return None
        if not isinstance(parsed, (list, tuple)):
            return None
        Model = self.env[model_name]
        if include_archived:
            Model = Model.with_context(active_test=False)
        try:
            return Model.search_count(list(parsed))
        except Exception:  # noqa: BLE001 - a bad ad-hoc domain must not 500
            return None

    # -- dashboard settings --------------------------------------------------
    def _can_edit(self):
        """True when the current user may change this board's settings/layout:
        the owner, or anyone in the builder group."""
        self.ensure_one()
        if self.env.user.has_group("eh_board.group_board_builder"):
            return True
        return self.owner_id.id == self.env.uid

    def get_settings(self):
        """Current dashboard settings + the option lists the settings panel
        needs (users to share with / to email)."""
        self.ensure_one()
        users = self.env["res.users"].search(
            [("share", "=", False), ("active", "=", True)], order="name")
        layout = self._active_layout()
        return {
            "id": self.id,
            "name": self.name or "",
            "description": self.description or "",
            "published": self.state == "published",
            "palette": self.palette or "default",
            "density": layout.density if layout else "comfortable",
            "default_date_preset": self.default_date_preset or "all",
            "refresh_mode": self.refresh_mode or "off",
            "refresh_interval": self.refresh_interval or 60,
            "digest_enabled": self.digest_enabled,
            "shared_user_ids": self.shared_user_ids.ids,
            "digest_user_ids": self.digest_user_ids.ids,
            "users": [{"id": u.id, "name": u.name} for u in users],
            "can_edit": self._can_edit(),
        }

    def save_settings(self, vals):
        """Apply settings from the in-app panel. Owner/builder only; layout
        density lives on the active layout, everything else on the board."""
        self.ensure_one()
        if not self._can_edit():
            from odoo.exceptions import AccessError
            raise AccessError(_("You may not change this dashboard's settings."))
        vals = dict(vals or {})
        density = vals.pop("density", None)
        published = vals.pop("published", None)
        write_vals = {k: v for k, v in vals.items() if k in self._fields}
        if published is not None:
            write_vals["state"] = "published" if published else "draft"
        if "shared_user_ids" in vals:
            write_vals["shared_user_ids"] = [(6, 0, vals["shared_user_ids"] or [])]
        if "digest_user_ids" in vals:
            write_vals["digest_user_ids"] = [(6, 0, vals["digest_user_ids"] or [])]
        self.write(write_vals)
        if density in ("comfortable", "compact"):
            layout = self._active_layout()
            if layout:
                layout.density = density
        return self.get_settings()

    def get_item_data(self, item_ids, options=None):
        """Refresh a subset of items (used by lazy load and live refresh)."""
        self.ensure_one()
        items = self.item_ids.filtered(lambda i: i.id in set(item_ids))
        return [item.get_payload(options or {}) for item in items]

    # -- server PDF report ---------------------------------------------------
    def _fmt_num(self, value, fmt="compact"):
        """Mirror the client number format for the server-rendered PDF."""
        v = value or 0.0
        if fmt == "plain":
            return "{:,.0f}".format(v)
        if fmt == "thousands":
            return "{:,.1f}K".format(v / 1000.0)
        if fmt == "millions":
            return "{:,.2f}M".format(v / 1000000.0)
        a = abs(v)
        if a >= 1e9:
            return "{:.1f}B".format(v / 1e9)
        if a >= 1e6:
            return "{:.1f}M".format(v / 1e6)
        if a >= 1e3:
            return "{:.1f}K".format(v / 1e3)
        return "{:,.0f}".format(v)

    def _report_data(self):
        """A render-friendly list of blocks for the QWeb PDF: KPI numbers, data
        tables (charts / list / pivot) and content. Numbers are pre-formatted so
        the template stays declarative and wkhtmltopdf renders pure HTML."""
        self.ensure_one()
        blocks = []
        for item in self.item_ids:
            payload = item.get_payload({})
            title = item.title or item.item_type
            fmt = payload.get("number_format", "compact")
            if payload.get("error"):
                blocks.append({"title": title, "kind": "error", "text": payload["error"]})
            elif payload.get("category") == "content":
                blocks.append({"title": title, "kind": "content",
                               "html": payload.get("content", "")})
            elif payload.get("category") == "kpi":
                unit = payload.get("unit") or ""
                value = self._fmt_num(payload.get("value", 0), fmt)
                if unit:
                    value = "%s %s" % (value, unit)
                blk = {"title": title, "kind": "kpi", "value": value}
                if payload.get("target"):
                    blk["target"] = self._fmt_num(payload["target"], fmt)
                blocks.append(blk)
            else:
                keys = payload.get("measure_keys", [])
                columns = [s.get("label", "Value") for s in payload.get("series", [])]
                rows = []
                for r in payload.get("rows", []):
                    label = " / ".join(str(l) for l in (r.get("labels") or []) if l not in (None, ""))
                    rows.append([label or "-"] + [
                        self._fmt_num(r.get("values", {}).get(k, 0), fmt) for k in keys])
                blocks.append({"title": title, "kind": "table",
                               "columns": columns, "rows": rows})
        return blocks

    def get_item_drilled(self, item_id, path, options=None):
        """Payload for one widget drilled to the given click path (breadcrumb)."""
        self.ensure_one()
        item = self.item_ids.filtered(lambda i: i.id == item_id)
        if not item:
            return {"id": item_id, "error": "Unknown widget."}
        return item.get_drilled_payload(path or [], options or {})

    def get_item_decomp(self, item_id, path, options=None):
        """One level of a decomposition tree for the given widget + click path."""
        self.ensure_one()
        item = self.item_ids.filtered(lambda i: i.id == item_id)
        if not item:
            return {"nodes": [], "error": "Unknown widget."}
        return item.get_decomp(path or [], options or {})

    # -- insights -----------------------------------------------------------
    def get_insights(self):
        """Plain-language read-outs of each data widget - offline and always on.
        A BYO-key LLM can later rewrite these through the same seam."""
        self.ensure_one()
        out = []
        for item in self.item_ids:
            if not item.datasource_id:
                continue
            text = item._insight_text()
            if text:
                out.append({"title": item.title or item.item_type, "text": text})
            # Key-influencers-lite: the biggest single driver of the measure.
            inf = item._influencer_text()
            if inf:
                out.append({"title": (item.title or item.item_type) + " · top contributor", "text": inf})
        return out

    @api.model
    def ai_available(self):
        """Client passthrough: is the optional BYO-key LLM configured?"""
        return self.env["eh.board.ai"].ai_available()

    def get_ai_insights(self):
        """Offline-first insights, optionally rewritten into an executive
        narrative by the customer's own LLM. The offline list is ALWAYS
        returned; the narrative is a best-effort extra that silently degrades.

        Only verified, already-computed facts are sent to the LLM - never raw
        record rows, credentials, the database name, or any SQL."""
        self.ensure_one()
        insights = self.get_insights()
        result = {"source": "offline", "narrative": "", "insights": insights}
        AI = self.env["eh.board.ai"]
        if not insights or not AI.ai_available():
            return result
        facts = ["%s: %s" % (i["title"], i["text"]) for i in insights]
        narrative = AI._narrate(facts)
        if narrative:
            cfg = AI._provider_config()
            result.update({
                "source": "llm",
                "narrative": narrative,
                "provider": cfg.get("provider"),
            })
        return result

    def _as_owner(self):
        """This dashboard bound to its owner's environment, so automated
        aggregation (snapshots, digests) respects the owner's record rules
        instead of leaking data as superuser."""
        self.ensure_one()
        owner = self.owner_id
        if owner and owner.active and owner.id != self.env.uid:
            return self.with_user(owner)
        return self

    # -- snapshots + digest -------------------------------------------------
    def capture_snapshot(self):
        """Record each data widget's headline value with a timestamp."""
        self.ensure_one()
        Snap = self.env["eh.board.snapshot"]
        now = fields.Datetime.now()
        for item in self.item_ids:
            if not item.datasource_id:
                continue
            payload = item.get_payload({})
            if payload.get("error"):
                continue
            if payload.get("category") == "kpi":
                value = payload.get("value", 0.0)
            elif payload.get("series"):
                first = payload["series"][0]["data"] if payload["series"] else []
                value = sum(first)
            else:
                continue
            Snap.create({
                "dashboard_id": self.id, "item_id": item.id,
                "value": value, "captured_on": now,
                "label": item.title or item.item_type})
        return True

    def send_digest(self):
        """Email this dashboard as a PDF to its configured recipients.

        Owner/builder only, and the recipient list is ALWAYS the board's own
        configured digest recipients (never a caller-supplied list) so this
        public method can't be turned into a mail relay.

        The PDF is attached when wkhtmltopdf is available; the mail still goes
        out with a summary body otherwise, so a digest is never silently lost.
        """
        self.ensure_one()
        if not self._can_edit():
            from odoo.exceptions import AccessError
            raise AccessError(_("You may not send this dashboard's digest."))
        recipients = self.digest_user_ids or self.owner_id
        emails = [u.email for u in recipients if u.email]
        if not emails:
            return False
        attachments = []
        try:
            report = self.env.ref("eh_board.action_report_eh_board_dashboard")
            # Do NOT bind the throwaway to ``_``: that rebinds the translation
            # function to a function-local, so the earlier ``raise AccessError(_())``
            # branch would hit UnboundLocalError instead of a clean AccessError.
            pdf, _content_type = report._render_qweb_pdf(report.report_name, self.ids)
            att = self.env["ir.attachment"].create({
                "name": "%s.pdf" % self.name, "type": "binary",
                "raw": pdf, "mimetype": "application/pdf"})
            attachments = [att.id]
        except Exception:  # noqa: BLE001 - PDF is best-effort
            _logger.info("eh_board digest PDF skipped (wkhtmltopdf unavailable?)")
        from markupsafe import escape
        safe_name = escape(self.name or "")
        mail = self.env["mail.mail"].sudo().create({
            "subject": "Dashboard: %s" % (self.name or ""),
            # Escape the name into the HTML body so a board titled
            # "<script>..." cannot inject markup into the recipient's inbox.
            "body_html": "<p>Your dashboard <b>%s</b> is ready.</p>" % safe_name,
            "email_to": ",".join(emails),
            "attachment_ids": [(6, 0, attachments)],
        })
        try:
            mail.send()
        except Exception:  # noqa: BLE001 - queued if no mail server
            _logger.info("eh_board digest queued")
        return mail.id

    @api.model
    def _cron_send_digests(self):
        for dash in self.search([("digest_enabled", "=", True)]):
            # An archived (or missing) regular owner makes _as_owner() fall
            # through to the cron's SUPERUSER env, which would email full-database
            # figures with every record rule bypassed. Skip those - a digest must
            # never leak data the owner could not see. A board owned by the system
            # user (no narrower identity) is left to send normally.
            owner = dash.owner_id
            if owner and not owner.active and owner.id != SUPERUSER_ID:
                _logger.info("eh_board digest skipped: dashboard %s owner inactive", dash.id)
                continue
            # Savepoint per board: a late failure rolls back only this board's
            # mail/attachment rows, not every digest already prepared this run.
            try:
                # Render + send as the owner so the emailed figures respect the
                # owner's record rules, not the superuser cron's.
                with self.env.cr.savepoint():
                    dash._as_owner().send_digest()
            except Exception:  # noqa: BLE001
                _logger.exception("eh_board digest skipped for %s", dash.id)
        return True

    # -- templates ----------------------------------------------------------
    def get_templates(self):
        """Available templates for the in-board gallery picker."""
        return self.env["eh.board.template"].gallery()

    def apply_template(self, template_id):
        """Create a new dashboard from a template and return an action to open it."""
        tmpl = self.env["eh.board.template"].browse(template_id)
        if not tmpl.exists():
            return {"error": "Unknown template."}
        return tmpl.apply_and_open()

    def save_as_template(self, name=None):
        """Serialise this live board into a reusable template (string model /
        field refs, so it can be re-applied on any database)."""
        self.ensure_one()
        layout = self._active_layout()
        grid = (layout.grid if layout else {}) or {}
        items = []
        for item in self.item_ids:
            g = grid.get(str(item.id), {})
            spec = {
                "type": item.item_type, "title": item.title or "",
                "x": g.get("x", 0), "y": g.get("y", 0),
                "w": g.get("w", 4), "h": g.get("h", 6),
            }
            for key, val in (("accent", item.accent), ("tile_style", item.tile_style),
                             ("icon", item.icon), ("content", item.content)):
                if val:
                    spec[key] = val
            if item.domain and item.domain != "[]":
                spec["domain"] = item.domain
            if item.datasource_id:
                spec["model"] = item.datasource_id.model_name
                spec["measures"] = [{
                    "verb": m.aggregate, "field": m.field_name or None,
                    "number_format": m.number_format, "unit": m.unit or "",
                    "target": m.target_value or 0.0, "compare_mode": m.compare_mode,
                    "as_line": bool(m.as_line),
                } for m in item.measure_ids]
                if item.primary_dimension_id:
                    spec["dimension"] = item.primary_dimension_id.name
                if item.secondary_dimension_id:
                    spec["secondary_dimension"] = item.secondary_dimension_id.name
                if item.date_granularity:
                    spec["granularity"] = item.date_granularity
            items.append(spec)
        filters = [{
            "name": f.name,
            "model": f.field_id.model_id.model if f.field_id else None,
            "field": f.field_id.name if f.field_id else None,
        } for f in self.filter_ids if f.filter_type == "field" and f.field_id]
        tmpl = self.env["eh.board.template"].create({
            "name": name or ("%s template" % self.name),
            "category": "general", "is_predefined": False,
            "description": "Saved from %s" % self.name,
            "payload": {"name": self.name, "items": items, "filters": filters},
        })
        return {"template_id": tmpl.id, "name": tmpl.name}

    def save_layout(self, grid, density=None):
        """Persist the grid geometry onto the active layout version."""
        self.ensure_one()
        layout = self._active_layout()
        if not layout:
            layout = self.env["eh.board.layout.version"].create({
                "dashboard_id": self.id,
                "name": "Default",
                "is_active": True,
                "is_default": True,
            })
            self.active_layout_id = layout
        layout.write({"grid": grid or {}, **({"density": density} if density else {})})
        return True

    # ----------------------------------------------------------- builder API
    def _create_item_from_builder(self, vals):
        """Create an item from the in-canvas builder shortcut vals.

        ``vals`` may carry ``model_id`` + ``measure`` + ``dimension`` shortcuts,
        in which case a data source and measure are spun up so the user never
        leaves the canvas. Returns the created ``eh.board.item`` record.
        """
        self.ensure_one()
        # A widget's dashboard_id is NOT NULL; refuse a non-persisted (NewId)
        # dashboard with a clear message instead of a raw not-null violation.
        if not self.id:
            raise UserError(_("Save the dashboard before adding a widget."))
        item_vals = self._builder_item_vals(vals)
        return self.env["eh.board.item"].create(item_vals)

    def _builder_item_vals(self, vals):
        """Translate builder shortcut vals into eh.board.item write values,
        spinning up the data source + measures. Handles a single measure or a
        list, a secondary dimension, and field-name -> id conversions."""
        vals = dict(vals)
        Item = self.env["eh.board.item"]
        model_id = vals.pop("model_id", None)
        measure = vals.pop("measure", None)
        measures = vals.pop("measures", None)
        dimension = vals.pop("dimension", None)
        secondary = vals.pop("secondary_dimension", None)
        granularity = vals.pop("granularity", None)
        drill_field = vals.pop("drill_field", None)
        date_field = vals.pop("date_field", None)
        sort_field = vals.pop("sort_field", None)
        item_vals = {k: v for k, v in vals.items() if k in Item._fields}
        # Authoritative: set dashboard_id AFTER the client-vals merge so a stray
        # dashboard_id in vals can never null it out.
        item_vals["dashboard_id"] = self.id
        if model_id and item_vals.get("item_type") not in ("richtext", "todo"):
            source = self._ensure_datasource(model_id)
            item_vals["datasource_id"] = source.id
            specs = measures if isinstance(measures, list) and measures else (
                [measure] if measure else [])
            ids = [self._ensure_measure(source, m).id for m in specs if m]
            if ids:
                item_vals["measure_ids"] = [(6, 0, ids)]
            if dimension:
                item_vals["primary_dimension_id"] = self._field_id(model_id, dimension)
            if secondary:
                item_vals["secondary_dimension_id"] = self._field_id(model_id, secondary)
            if drill_field:
                item_vals["drill_field_id"] = self._field_id(model_id, drill_field)
            if date_field:
                item_vals["date_filter_field_id"] = self._field_id(model_id, date_field)
            if sort_field:
                item_vals["sort_field_id"] = self._field_id(model_id, sort_field)
            if granularity:
                item_vals["date_granularity"] = granularity
        return item_vals

    def add_item(self, vals):
        self.ensure_one()
        item = self._create_item_from_builder(vals)
        return {"meta": item._meta(), "payload": item.get_payload()}

    def get_item_config(self, item_id):
        """Return the builder config of an existing item so the luxury builder
        can open pre-filled for editing (instead of the raw backend form)."""
        self.ensure_one()
        item = self.env["eh.board.item"].browse(item_id)
        measures = [{
            "verb": m.aggregate,
            "field": m.field_name or "",
            "number_format": m.number_format,
            "unit": m.unit or "",
            "formula": m.formula or "",
            "as_line": bool(m.as_line),
        } for m in item.measure_ids]
        first = item.measure_ids[:1]
        return {
            "item_type": item.item_type,
            "title": item.title or "",
            "model_id": item.datasource_id.model_id.id if item.datasource_id else False,
            "model_name": item.datasource_id.model_name if item.datasource_id else "",
            "domain": item.domain or "[]",
            "measures": measures,
            "verb": first.aggregate if first else "count",
            "measure_field": (first.field_name or "") if first else "",
            "dimension": item.primary_dimension_id.name if item.primary_dimension_id else "",
            "secondary_dimension": item.secondary_dimension_id.name if item.secondary_dimension_id else "",
            "granularity": item.date_granularity or "month",
            "accent": item._resolved_accent(),
            "tile_style": item.tile_style or "soft",
            "content": item.content or "",
            "sort_mode": item.sort_mode or "value_desc",
            "sort_field": item.sort_field_id.name if item.sort_field_id else "",
            "sort_order": item.sort_order or "desc",
            "record_limit": item.record_limit or 0,
            "record_limit_visibility": item.record_limit_visibility,
            "include_archived": item.include_archived,
            "number_format": first.number_format if first else "compact",
            "target": first.target_value if first else 0.0,
            "compare": (first.compare_mode or "none") if first else "none",
            "show_legend": item.show_legend,
            "show_values": item.show_values,
            "show_grid": item.show_grid,
            "semi_circle": item.semi_circle,
            "stacked": item.stacked,
            "smooth": item.smooth,
            "goal_value": item.goal_value,
            "combo_line": item.combo_line,
            "data_label_type": item.data_label_type or "value",
            "cumulative": item.cumulative,
            "fill_gaps": item.fill_gaps,
            "group_others": item.group_others,
            "click_action": item.click_action or "records",
            "drill_field": item.drill_field_id.name if item.drill_field_id else "",
            "date_field": item.date_filter_field_id.name if item.date_filter_field_id else "",
            "default_date_filter": item.default_date_filter or "none",
            "description": item.description or "",
            "conditional_rules": item.conditional_rules or [],
        }

    def update_item_from_builder(self, item_id, vals):
        """Apply builder config back onto an existing item (in-canvas edit)."""
        self.ensure_one()
        item = self.env["eh.board.item"].browse(item_id)
        write_vals = self._builder_item_vals(vals)
        write_vals.pop("dashboard_id", None)
        # explicit clears when the builder sent an empty dimension
        if not vals.get("dimension"):
            write_vals["primary_dimension_id"] = False
        if not vals.get("secondary_dimension"):
            write_vals["secondary_dimension_id"] = False
        if not vals.get("sort_field"):
            write_vals["sort_field_id"] = False
        item.write(write_vals)
        return {"meta": item._meta(), "payload": item.get_payload()}

    def _ensure_datasource(self, model_id):
        Source = self.env["eh.board.datasource"]
        existing = Source.search(
            [("model_id", "=", model_id), ("provider_type", "=", "orm")], limit=1)
        if existing:
            return existing
        model = self.env["ir.model"].browse(model_id)
        return Source.create({
            "name": model.name or model.model,
            "provider_type": "orm",
            "model_id": model_id,
        })

    def _ensure_measure(self, source, measure):
        Measure = self.env["eh.board.measure"]
        field_name = measure.get("field")
        verb = measure.get("verb", "count")
        field_id = self._field_id(source.model_id.id, field_name) if field_name else False
        fmt = measure.get("number_format") or "compact"
        unit = measure.get("unit") or ""
        target = float(measure.get("target") or 0.0)
        compare = measure.get("compare_mode") or "none"
        formula = measure.get("formula") or ""
        as_line = bool(measure.get("as_line"))
        # Dedup on the full presentation, not just the aggregation: a measure
        # with a target or a different format/unit is a distinct measure, so two
        # widgets never share (and clobber) each other's goal or formatting.
        existing = source.measure_ids.filtered(
            lambda m: m.aggregate == verb
            and (m.field_id.id if m.field_id else False) == (field_id or False)
            and (m.number_format or "compact") == fmt
            and (m.unit or "") == unit
            and float(m.target_value or 0.0) == target
            and (m.compare_mode or "none") == compare
            and bool(m.as_line) == as_line
            and (m.formula or "") == formula)
        if existing:
            return existing[:1]
        name = measure.get("label") or (
            "Calculated" if verb == "formula"
            else (field_name.replace("_", " ").title() if field_name else "Records"))
        return Measure.create({
            "name": name,
            "datasource_id": source.id,
            "field_id": field_id or False,
            "aggregate": verb,
            "formula": formula,
            "number_format": fmt,
            "unit": unit,
            "target_value": target,
            "compare_mode": compare,
            "as_line": as_line,
        })

    def _field_id(self, model_id, field_name):
        if not field_name:
            return False
        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model_id), ("name", "=", field_name)], limit=1)
        return field.id or False

    def update_item(self, item_id, vals):
        self.ensure_one()
        item = self.env["eh.board.item"].browse(item_id)
        item.write({k: v for k, v in vals.items() if k in item._fields})
        return {"meta": item._meta(), "payload": item.get_payload()}

    def delete_item(self, item_id):
        self.ensure_one()
        self.env["eh.board.item"].browse(item_id).unlink()
        return True

    def duplicate_item(self, item_id):
        """Clone a widget (copy config, place it just after the original)."""
        self.ensure_one()
        item = self.env["eh.board.item"].browse(item_id)
        clone = item.copy({
            "title": (item.title or item.item_type) + " (copy)",
            "sequence": item.sequence + 1,
        })
        return {"meta": clone._meta(), "payload": clone.get_payload()}

    def add_filter(self, vals):
        """Create a global field filter from the in-canvas add-filter dialog."""
        self.ensure_one()
        model_id = vals.get("model_id")
        field_name = vals.get("field")
        if not (model_id and field_name):
            return {"error": "Pick a model and a field."}
        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model_id), ("name", "=", field_name)], limit=1)
        if not field:
            return {"error": "Unknown field."}
        flt = self.env["eh.board.filter"].create({
            "dashboard_id": self.id,
            "name": vals.get("name") or field.field_description or field.name,
            "filter_type": "field",
            "field_id": field.id,
        })
        return {"filter": flt.spec()}

    def remove_filter(self, filter_id):
        self.ensure_one()
        self.env["eh.board.filter"].browse(filter_id).unlink()
        return True

    def get_builder_meta(self):
        """Models and their groupable / measurable fields for the add dialog."""
        self.ensure_one()
        models = self.env["ir.model"].sudo().search([
            ("transient", "=", False),
            ("model", "not like", "ir.%"),
            ("model", "not like", "bus.%"),
        ])
        allowed = []
        for model in models:
            if model.model not in self.env:
                continue
            Model = self.env[model.model]
            # Include every concrete, queryable model - crucially the analytical
            # SQL-VIEW report models (sale.report, account.invoice.report,
            # pos.order.report, ...) which have _auto=False but a real table and
            # full _read_group support. Only ABSTRACT mixins (no table) are
            # excluded here; transient wizards are already filtered above.
            if not Model._abstract and not Model._transient:
                allowed.append({"id": model.id, "model": model.model, "name": model.name})
        return {"models": sorted(allowed, key=lambda m: m["name"])}

    def preview_item(self, vals):
        """Build a payload + meta from unsaved builder config, WITHOUT
        persisting. Creates real records inside a savepoint (so measures link
        and validation is exact), computes the payload, then rolls everything
        back. Drives the live preview in the add-widget builder."""
        self.ensure_one()
        item_type = vals.get("item_type", "bar")
        if item_type not in ("richtext", "todo") and not vals.get("model_id"):
            return {"meta": None, "payload": {"error": "Choose a data source to preview."}}

        out = {"meta": None, "payload": {"error": "Configure a widget to preview it."}}

        class _Abort(Exception):
            pass

        try:
            with self.env.cr.savepoint():
                item = self._create_item_from_builder(vals)
                out = {"meta": item._meta(), "payload": item.get_payload()}
                raise _Abort()  # discard the preview records
        except _Abort:
            pass
        except Exception as err:  # noqa: BLE001 - preview never crashes the dialog
            out = {"meta": None, "payload": {"error": str(err)}}
        return out

    def get_model_fields(self, model_id):
        """Groupable dimensions and aggregatable measures for one model."""
        self.ensure_one()
        Fields = self.env["ir.model.fields"].sudo()
        fields = Fields.search([("model_id", "=", model_id), ("store", "=", True)])
        dimensions, measures = [], []
        for f in fields:
            if f.ttype in ("many2one", "selection", "date", "datetime", "boolean", "char"):
                dimensions.append({"name": f.name, "label": f.field_description,
                                   "ttype": f.ttype})
            if f.ttype in ("integer", "float", "monetary"):
                measures.append({"name": f.name, "label": f.field_description,
                                 "ttype": f.ttype})
        return {
            "dimensions": sorted(dimensions, key=lambda x: x["label"] or x["name"]),
            "measures": sorted(measures, key=lambda x: x["label"] or x["name"]),
        }

    # --------------------------------------------------------------- actions
    def action_open_board(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "eh_board.board",
            "name": self.name,
            "params": {"dashboard_id": self.id},
        }
