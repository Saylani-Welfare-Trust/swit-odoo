from odoo import api, models
from odoo.osv import expression

# Technical registries. A document the user can open and approve has a form view
# and is not one of these.
_TECHNICAL_PREFIXES = (
    "ir.",
    "bus.",
    "base.",
    "base_import.",
    "web_editor.",
    "web_tour.",
    "auth.",
    "approval.",
    "onboarding.",
    "iap.",
    "privacy.",
)


class IrModel(models.Model):
    _inherit = "ir.model"

    @api.depends("name", "model")
    @api.depends_context("approval_target_model")
    def _compute_display_name(self):
        if not self.env.context.get("approval_target_model"):
            return super()._compute_display_name()
        for model in self:
            model.display_name = "%s (%s)" % (model.name, model.model)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.context.get("approval_target_model"):
            domain = expression.AND([domain or [], self._approval_target_domain()])
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def _approval_target_domain(self):
        return [("model", "in", self._approval_target_model_names())]

    @api.model
    def _approval_target_model_names(self):
        """Technical names of concrete documents that have a form view."""
        self.env.cr.execute(
            "SELECT DISTINCT model FROM ir_ui_view WHERE type = 'form' AND model IS NOT NULL"
        )
        names = []
        for (name,) in self.env.cr.fetchall():
            if not name or name.startswith(_TECHNICAL_PREFIXES):
                continue
            Model = self.env.get(name)
            if Model is None or Model._abstract or Model._transient:
                continue
            names.append(name)
        return names
