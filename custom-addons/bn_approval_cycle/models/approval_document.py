import re

from lxml import etree

from odoo import _, fields, models
from odoo.tools import sql

STAT_BUTTON = "action_view_approval_requests"
_METHOD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Base(models.AbstractModel):
    _inherit = "base"

    approval_request_count = fields.Integer(compute="_compute_approval_request_count")
    approval_locked_methods = fields.Char(compute="_compute_approval_locked_methods")

    def _compute_approval_request_count(self):
        counts = {}
        if self.ids and sql.table_exists(self.env.cr, "approval_request"):
            grouped = self.env["approval.request"]._read_group(
                [("model_name", "=", self._name), ("res_id", "in", self.ids)],
                ["res_id"],
                ["__count"],
            )
            counts = {res_id: count for res_id, count in grouped}
        for record in self:
            record.approval_request_count = counts.get(record.id, 0)

    def _compute_approval_locked_methods(self):
        """Comma-separated button methods hidden while a request for them is pending."""
        methods_by_res = {}
        if self.ids and sql.table_exists(self.env.cr, "approval_request"):
            pending = self.env["approval.request"].sudo().search([
                ("model_name", "=", self._name),
                ("res_id", "in", self.ids),
                ("state", "=", "pending"),
            ])
            for request in pending:
                if request.method_name:
                    methods_by_res.setdefault(request.res_id, set()).add(request.method_name)
        for record in self:
            record.approval_locked_methods = ",".join(sorted(methods_by_res.get(record.id, ())))

    def action_view_approval_requests(self):
        """Open the approval requests raised for this document."""
        self.ensure_one()
        domain = [("model_name", "=", self._name), ("res_id", "=", self.id)]
        requests = self.env["approval.request"].search(domain)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Approval Requests"),
            "res_model": "approval.request",
            "domain": domain,
            "context": {"create": False},
            "target": "current",
        }
        if len(requests) == 1:
            action.update({
                "view_mode": "form",
                "res_id": requests.id,
                "views": [(False, "form")],
            })
        else:
            action.update({
                "view_mode": "tree,form",
                "views": [(False, "tree"), (False, "form")],
            })
        return action

    def _approval_stat_button_applies(self):
        """True when this model has an approval rule or an existing request."""
        if self._transient or self._abstract or self._name.startswith("approval."):
            return False
        cr = self.env.cr
        if sql.table_exists(cr, "approval_rule"):
            cr.execute(
                """
                SELECT 1
                  FROM approval_rule rule
                  JOIN ir_model model ON model.id = rule.model_id
                 WHERE model.model = %s
                 LIMIT 1
                """,
                (self._name,),
            )
            if cr.fetchone():
                return True
        if sql.table_exists(cr, "approval_request"):
            cr.execute(
                "SELECT 1 FROM approval_request WHERE model_name = %s LIMIT 1",
                (self._name,),
            )
            return bool(cr.fetchone())
        return False

    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        if view_type == "form":
            key += (self._approval_stat_button_applies(), self._approval_gated_method_names())
        return key

    def _approval_gated_method_names(self):
        """Button methods protected by a rule on this model."""
        if self._transient or self._abstract or self._name.startswith("approval."):
            return ()
        names = set()
        if sql.table_exists(self.env.cr, "approval_rule"):
            self.env.cr.execute(
                """
                SELECT DISTINCT rule.method_name
                  FROM approval_rule rule
                  JOIN ir_model model ON model.id = rule.model_id
                 WHERE model.model = %s
                   AND COALESCE(rule.method_name, '') != ''
                """,
                (self._name,),
            )
            names.update(row[0] for row in self.env.cr.fetchall())
        return tuple(sorted(name for name in names if name and _METHOD_RE.match(name)))

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != "form":
            return arch, view
        self._hide_gated_buttons(arch)
        if not self._approval_stat_button_applies():
            return arch, view
        if arch.find(".//button[@name='%s']" % STAT_BUTTON) is not None:
            return arch, view
        button = etree.fromstring(
            """
            <button name="action_view_approval_requests" type="object"
                    class="oe_stat_button" icon="fa-check-square-o"
                    groups="base.group_user"
                    invisible="approval_request_count == 0">
                <field name="approval_request_count" widget="statinfo" string="Approvals"/>
            </button>
            """
        )
        button_box = arch.find(".//div[@name='button_box']")
        if button_box is None:
            for node in arch.iter("div"):
                if "oe_button_box" in (node.get("class") or ""):
                    button_box = node
                    break
        if button_box is not None:
            button_box.append(button)
            return arch, view
        box = etree.Element("div", {"class": "oe_button_box", "name": "button_box"})
        box.append(button)
        sheet = arch.find(".//sheet")
        if sheet is not None:
            sheet.insert(0, box)
        else:
            arch.insert(0, box)
        return arch, view

    def _hide_gated_buttons(self, arch):
        """Hide a protected button while its approval request is still pending."""
        methods = set(self._approval_gated_method_names())
        if not methods:
            return
        hidden = False
        for node in arch.iter("button"):
            name = node.get("name") or ""
            if node.get("type") != "object" or name not in methods:
                continue
            lock = "',%s,' in (',' + (approval_locked_methods or '') + ',')" % name
            current = node.get("invisible")
            node.set("invisible", "(%s) or (%s)" % (lock, current) if current else lock)
            hidden = True
        if hidden and arch.find(".//field[@name='approval_locked_methods']") is None:
            field = etree.Element("field", {"name": "approval_locked_methods", "invisible": "1"})
            sheet = arch.find(".//sheet")
            (sheet if sheet is not None else arch).insert(0, field)
