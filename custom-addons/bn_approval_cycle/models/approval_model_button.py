import logging

from lxml import etree

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApprovalModelButton(models.Model):
    """A button on a document form that an approval rule can protect."""

    _name = "approval.model.button"
    _description = "Approval Form Button"
    _order = "is_header desc, sequence, id"
    _rec_names_search = ["label", "method"]

    model_id = fields.Many2one("ir.model", required=True, ondelete="cascade", index=True)
    method = fields.Char(required=True, index=True)
    label = fields.Char()
    is_header = fields.Boolean(string="Header Button")
    sequence = fields.Integer(default=0)

    _sql_constraints = [
        ("approval_model_button_uniq", "unique(model_id, method)",
         "Each button is listed once per document."),
    ]

    @api.depends("label", "method")
    def _compute_display_name(self):
        for button in self:
            if button.label:
                button.display_name = "%s (%s)" % (button.label, button.method)
            else:
                button.display_name = button.method or ""

    def _search(self, domain, offset=0, limit=None, order=None):
        # The dropdown has to list the form's current buttons, so refresh that
        # document before the search runs. The flag stops the refresh from
        # searching this same list again.
        if not self.env.context.get("approval_button_syncing"):
            model_id = self._model_id_from_domain(domain)
            if model_id:
                self._sync(model_id)
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def _model_id_from_domain(self, domain):
        for leaf in domain or []:
            if (
                isinstance(leaf, (list, tuple)) and len(leaf) == 3
                and leaf[0] == "model_id" and leaf[1] == "=" and isinstance(leaf[2], int)
            ):
                return leaf[2]
        return False

    def _sync(self, model_id):
        """Store the buttons currently on this document's form."""
        self = self.sudo().with_context(approval_button_syncing=True)
        model = self.env["ir.model"].browse(model_id).exists()
        if not model:
            return
        buttons = self._read_buttons(model.model)
        existing = self.search([("model_id", "=", model.id)])
        by_method = {row.method: row for row in existing}
        seen = set()
        for sequence, (method, label, is_header) in enumerate(buttons):
            seen.add(method)
            vals = {"label": label, "is_header": is_header, "sequence": sequence}
            row = by_method.get(method)
            if row:
                if row.label != label or row.is_header != is_header or row.sequence != sequence:
                    row.write(vals)
            else:
                self.create({"model_id": model.id, "method": method, **vals})
        stale = existing.filtered(lambda row: row.method not in seen)
        if stale:
            used = self.env["approval.rule"].sudo().search([("button_id", "in", stale.ids)]).button_id
            (stale - used).unlink()

    @api.model
    def _read_buttons(self, model_name):
        """[(method, label, is_header)] of the object's form buttons.

        Header buttons come first. Smart buttons are left out: those open
        related records and are not the operation the rule should protect.
        """
        if not model_name or model_name not in self.env:
            return []
        try:
            arch = self.env[model_name].sudo().get_view(view_type="form")["arch"]
            root = etree.fromstring(arch)
        except Exception:
            _logger.warning("Could not read the form of %s while listing approval buttons", model_name, exc_info=True)
            return []
        header, other, seen = [], [], set()
        Model = self.env[model_name]
        for node in root.iter("button"):
            name = node.get("name") or ""
            button_type = node.get("type")
            if not name or name.startswith("_") or name == "action_view_approval_requests" or name in seen:
                continue
            if button_type not in (None, "object"):
                continue
            if button_type is None and not callable(getattr(Model, name, None)):
                continue
            if "oe_stat_button" in (node.get("class") or ""):
                continue
            if self._button_in_box(node):
                continue
            seen.add(name)
            label = node.get("string") or node.get("title") or ""
            (header if self._button_in_header(node) else other).append(
                (name, label, self._button_in_header(node))
            )
        return header + other

    @staticmethod
    def _button_in_box(node):
        parent = node.getparent()
        while parent is not None:
            if parent.tag == "div" and (
                parent.get("name") == "button_box" or "oe_button_box" in (parent.get("class") or "")
            ):
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _button_in_header(node):
        parent = node.getparent()
        while parent is not None:
            if parent.tag == "header":
                return True
            parent = parent.getparent()
        return False
