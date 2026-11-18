from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import formatLang

_TRACKED_ON_RULE = (
    "role_id", "sequence", "required_approvals", "allow_requester",
    "condition_type", "minimum_amount", "maximum_amount", "note",
)


class ApprovalRuleLine(models.Model):
    _name = "approval.rule.line"
    _description = "Approval Rule Stage"
    _order = "sequence, id"
    _rec_names_search = ["role_id", "note"]

    rule_id = fields.Many2one("approval.rule", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="rule_id.currency_id")
    sequence = fields.Integer(default=10, required=True)
    role_id = fields.Many2one("approval.role", required=True, ondelete="restrict")
    required_approvals = fields.Integer(default=1, required=True)
    allow_requester = fields.Boolean(
        string="Allow Requester to Approve",
        default=False,
        help="If disabled, the requester cannot approve their own request.",
    )
    condition_type = fields.Selection(
        [("always", "Always"), ("amount", "Amount Threshold")],
        string="Required When",
        default="always",
        required=True,
    )
    minimum_amount = fields.Monetary(
        currency_field="currency_id",
        help="Used when Required When is Amount Threshold. The stage is required at or above this amount. Zero means no lower limit on the stage.",
    )
    maximum_amount = fields.Monetary(
        currency_field="currency_id",
        help="Used when Required When is Amount Threshold. The stage is not required above this amount. Zero means no upper limit on the stage.",
    )
    note = fields.Char()

    @api.depends("role_id.name", "condition_type", "minimum_amount", "maximum_amount", "currency_id")
    def _compute_display_name(self):
        for line in self:
            role = line.role_id.name or _("Stage")
            line.display_name = "%s — %s" % (role, line._threshold_label())

    def _threshold_label(self):
        self.ensure_one()
        if self.condition_type != "amount":
            return _("Always")
        currency = self.currency_id

        def money(amount):
            return formatLang(self.env, amount or 0.0, currency_obj=currency) if currency else amount

        if self.minimum_amount and self.maximum_amount:
            return _("%s to %s", money(self.minimum_amount), money(self.maximum_amount))
        if self.minimum_amount:
            return _("From %s", money(self.minimum_amount))
        if self.maximum_amount:
            return _("Up to %s", money(self.maximum_amount))
        return _("Any amount")

    @api.constrains("required_approvals", "sequence", "minimum_amount", "maximum_amount", "role_id")
    def _check_stage_values(self):
        for line in self:
            if line.required_approvals < 1:
                raise ValidationError(_("Each stage must require at least one approval."))
            if line.sequence < 0:
                raise ValidationError(_("Stage sequence cannot be negative."))
            if line.condition_type == "amount" and line.maximum_amount and line.maximum_amount < line.minimum_amount:
                raise ValidationError(_("The stage maximum amount cannot be lower than its minimum amount."))
            if line.role_id.approver_type == "department_manager" and line.required_approvals > 1:
                raise ValidationError(_(
                    "Role '%s' has one manager per department, so the stage cannot require more than one approval.",
                    line.role_id.display_name,
                ))

    def _track_value(self, field, value):
        if field.type == "many2one":
            return value.display_name if value else _("empty")
        if field.type == "selection":
            return dict(field._description_selection(self.env)).get(value) or _("empty")
        if field.type == "boolean":
            return _("Yes") if value else _("No")
        if value in (False, None, ""):
            return _("empty")
        return value

    def write(self, vals):
        keys = [key for key in _TRACKED_ON_RULE if key in vals]
        before = {line.id: {key: line[key] for key in keys} for line in self} if keys else {}
        result = super().write(vals)
        for line in self:
            old = before.get(line.id)
            if not old or not line.rule_id:
                continue
            changes = []
            for key, previous in old.items():
                current = line[key]
                if previous == current:
                    continue
                field = self._fields[key]
                changes.append(_(
                    "%(label)s: %(old)s → %(new)s",
                    label=field.string,
                    old=line._track_value(field, previous),
                    new=line._track_value(field, current),
                ))
            if changes:
                line.rule_id.message_post(
                    body=_("Stage %(role)s\n%(changes)s", role=line.role_id.display_name, changes="\n".join(changes)),
                    subtype_xmlid="mail.mt_note",
                )
        return result

    @api.onchange("condition_type")
    def _onchange_condition_type(self):
        if self.condition_type != "amount":
            self.minimum_amount = 0
            self.maximum_amount = 0

    def _applies(self, amount):
        self.ensure_one()
        if self.condition_type == "always":
            return True
        if amount < self.minimum_amount:
            return False
        return not (self.maximum_amount and amount > self.maximum_amount)
