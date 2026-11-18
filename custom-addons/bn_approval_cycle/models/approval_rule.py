import ast
import functools
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import sql

_logger = logging.getLogger(__name__)


def _make_gated(method_name, origin):
    """Wrap a model method so it goes through the approval gate."""

    @functools.wraps(origin)
    def gated(self, *args, **kwargs):
        if not self:
            return origin(self, *args, **kwargs)
        engine = self.env["approval.engine"]
        allowed, action = engine._gate(self, method_name)
        result = origin(allowed, *args, **kwargs) if allowed else True
        engine._consume(allowed, result, method_name)
        return action or result

    gated._approval_origin = origin
    return gated


class ApprovalRule(models.Model):
    _name = "approval.rule"
    _description = "Approval Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    sequence = fields.Integer(default=10, tracking=True, help="Rules are evaluated in this order; the first match wins.")
    model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('transient', '=', False)]",
        tracking=True,
        help="Document this rule protects. Search by its name, for example Sales Order, "
             "or by its technical name, for example sale.order.",
    )
    department_ids = fields.Many2many(
        "hr.department", "approval_rule_department_rel", "rule_id", "department_id",
        string="Departments",
        tracking=True,
        help="Apply this rule only to requests raised from these departments (and their sub-departments). "
             "Leave empty to apply to every department. Ignored when Department-wise Approval is off.",
    )
    department_wise_enabled = fields.Boolean(compute="_compute_department_wise_enabled")

    def _compute_department_wise_enabled(self):
        enabled = self.env["approval.engine"]._department_wise()
        for rec in self:
            rec.department_wise_enabled = enabled

    model_name = fields.Char(related="model_id.model", store=True, index=True)
    button_id = fields.Many2one(
        "approval.model.button",
        string="Button",
        ondelete="set null",
        domain="[('model_id', '=', model_id)]",
        tracking=True,
        help="Button this rule protects, taken from the document form. "
             "The last approval runs it with the rights of the person who submitted the document.",
    )
    method_name = fields.Char(
        string="Button Method",
        tracking=True,
        help="Technical name of the protected button, for example action_confirm. "
             "Filled in when a button is selected. Type it here only when the button is not in the list.",
    )
    company_id = fields.Many2one("res.company", tracking=True, help="Empty means all companies.")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True,
        tracking=True,
        help="Currency of a stage's Amount Threshold. Document amounts are converted to it before comparing.",
    )
    domain = fields.Char(
        string="Additional Conditions",
        default="[]",
        tracking=True,
        help="Extra filter on the document (e.g. only vendor bills). Empty means no extra condition.",
    )
    line_ids = fields.One2many(
        "approval.rule.line", "rule_id", string="Approval Stages", copy=True, tracking=True,
    )

    @api.constrains("line_ids", "active")
    def _check_stages(self):
        for rule in self.filtered("active"):
            if not rule.line_ids:
                raise ValidationError(_("An active approval rule must have at least one approval stage."))
            inactive = rule.line_ids.role_id.filtered(lambda role: not role.active)
            if inactive:
                raise ValidationError(_(
                    "Activate %(roles)s, or remove them from rule '%(rule)s'. An inactive role cannot approve.",
                    roles=", ".join(inactive.mapped("name")), rule=rule.name,
                ))

    @api.constrains("model_name")
    def _check_target_model(self):
        allowed = set(self.env["ir.model"]._approval_target_model_names())
        for rule in self:
            if rule.model_name and rule.model_name not in allowed:
                raise ValidationError(_(
                    "'%(model)s' cannot be used as a target model. Choose a document that has a form, such as a sales order or a bill.",
                    model=rule.model_name,
                ))

    @api.constrains("model_id", "button_id")
    def _check_button_model(self):
        for rule in self:
            if rule.button_id and rule.button_id.model_id != rule.model_id:
                raise ValidationError(_("The button does not belong to %s.", rule.model_id.display_name))

    @api.constrains("domain")
    def _check_domain(self):
        for rule in self:
            try:
                domain = ast.literal_eval(rule.domain or "[]")
                if not isinstance(domain, list):
                    raise ValueError
                if rule.model_name:
                    self.env[rule.model_name].sudo().search_count(domain)
            except Exception:
                raise ValidationError(_("The additional conditions of rule '%s' are not a valid filter.", rule.name))

    @api.onchange("model_id")
    def _onchange_model_id(self):
        self.button_id = False
        names = [
            method for method, _label, _header
            in self.env["approval.model.button"]._read_buttons(self.model_name)
        ]
        if self.method_name not in names:
            self.method_name = False
        # A filter written for the previous document is not valid on the new one,
        # and the domain editor errors when it still points at the old fields.
        if self.domain and self.domain != "[]":
            self.domain = "[]"

    @api.onchange("button_id")
    def _onchange_button_id(self):
        if self.button_id:
            self.method_name = self.button_id.method

    def _copy_method_from_button(self, vals):
        if vals.get("button_id"):
            button = self.env["approval.model.button"].browse(vals["button_id"])
            if button:
                vals["method_name"] = button.method

    @api.constrains("model_name", "method_name")
    def _check_supported_operation(self):
        for rule in self:
            rule._check_custom_method()

    def _check_custom_method(self):
        self.ensure_one()
        name = self.method_name or ""
        if not name:
            raise ValidationError(_("Set the button that rule '%s' protects.", self.name))
        if not name.isidentifier() or name.startswith("_"):
            raise ValidationError(_("'%s' is not a public method name.", name))
        if hasattr(models.BaseModel, name):
            raise ValidationError(_("'%s' is a standard ORM method and cannot be protected.", name))
        if self.model_name not in self.env or not callable(getattr(self.env[self.model_name], name, None)):
            raise ValidationError(_("'%(model)s' has no method '%(method)s'.", model=self.model_name, method=name))

    # ------------------------------------------------------------------
    # Runtime patching of 'Other Button' methods
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        self._drop_retired_extension_views()
        self._patch_custom_methods()

    def _drop_retired_extension_views(self):
        """Remove settings extensions left behind by the retired split modules.

        Those modules were only marked uninstalled. Their views still extend
        Settings and look for a block that no longer exists, which makes the
        whole Settings screen fail to open.
        """
        retired = (
            "bn_approval_cycle_sale",
            "bn_approval_cycle_purchase",
            "bn_approval_cycle_account",
            "bn_approval_cycle_stock",
            "bn_approval_cycle_expense",
            "bn_approval_cycle_timeoff",
            "bn_approval_cycle_mrp",
            "bn_approval_cycle_repair",
        )
        cr = self.env.cr
        cr.execute(
            """
            DELETE FROM ir_ui_view
             WHERE id IN (
                    SELECT res_id
                      FROM ir_model_data
                     WHERE module IN %s
                       AND model = 'ir.ui.view'
                  )
            """,
            (retired,),
        )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module IN %s AND model = 'ir.ui.view'",
            (retired,),
        )

    def _unregister_hook(self):
        self._unpatch_custom_methods()
        super()._unregister_hook()

    def _patch_custom_methods(self):
        rules = self.sudo().with_context(active_test=True).search([("method_name", "!=", False)])
        for model_name, method_name in {(r.model_name, r.method_name) for r in rules}:
            Model = self.env.registry.get(model_name)
            if Model is None or not method_name or method_name.startswith("_") \
                    or hasattr(models.BaseModel, method_name):
                continue
            if hasattr(Model.__dict__.get(method_name), "_approval_origin"):
                continue
            origin = getattr(Model, method_name, None)
            if not callable(origin):
                _logger.warning("Approval rule targets missing method %s.%s", model_name, method_name)
                continue
            gated = _make_gated(method_name, origin)
            gated._approval_own = method_name in Model.__dict__
            setattr(Model, method_name, gated)

    def _unpatch_custom_methods(self):
        for Model in self.env.registry.values():
            for name, func in list(Model.__dict__.items()):
                if hasattr(func, "_approval_origin"):
                    if func._approval_own:
                        setattr(Model, name, func._approval_origin)
                    else:
                        delattr(Model, name)

    def _update_registry(self):
        """Re-patch this worker now and make the other workers reload their registry."""
        if self.env.registry.ready and not self.env.context.get("import_file"):
            self._unpatch_custom_methods()
            self._patch_custom_methods()
            self.env.registry.registry_invalidated = True

    def _auto_init(self):
        """Copy a button name from the old operation column before that column is removed."""
        cr = self.env.cr
        if sql.column_exists(cr, "approval_rule", "operation"):
            legacy = {
                ("sale.order", "confirm"): "action_confirm",
                ("purchase.order", "confirm"): "button_confirm",
                ("account.move", "post"): "action_post",
                ("account.payment", "post"): "action_post",
                ("stock.picking", "validate"): "button_validate",
                ("hr.expense.sheet", "approve"): "action_approve_expense_sheets",
                ("hr.leave", "approve"): "action_approve",
                ("hr.leave.allocation", "approve"): "action_approve",
                ("mrp.production", "confirm"): "action_confirm",
                ("repair.order", "validate"): "action_validate",
            }
            cr.execute("""
                SELECT rule.id, model.model, rule.operation, COALESCE(rule.method_name, '')
                  FROM approval_rule rule
                  JOIN ir_model model ON model.id = rule.model_id
            """)
            for rule_id, model_name, operation, method_name in cr.fetchall():
                if method_name:
                    continue
                method_name = legacy.get((model_name, operation))
                if not method_name:
                    continue
                cr.execute(
                    "UPDATE approval_rule SET method_name = %s WHERE id = %s",
                    (method_name, rule_id),
                )
            if sql.column_exists(cr, "approval_request", "method_name"):
                cr.execute("""
                    UPDATE approval_request req
                       SET method_name = rule.method_name
                      FROM approval_rule rule
                     WHERE req.rule_id = rule.id
                       AND COALESCE(req.method_name, '') = ''
                       AND COALESCE(rule.method_name, '') != ''
                """)
        super()._auto_init()

    def init(self):
        """Retire the split modules and the settings views they left behind."""
        retired = (
            "bn_approval_cycle_sale",
            "bn_approval_cycle_purchase",
            "bn_approval_cycle_account",
            "bn_approval_cycle_stock",
            "bn_approval_cycle_expense",
            "bn_approval_cycle_timeoff",
            "bn_approval_cycle_mrp",
            "bn_approval_cycle_repair",
        )
        cr = self.env.cr
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'uninstalled'
             WHERE name IN %s
               AND state IN ('installed', 'to upgrade', 'to remove')
            """,
            (retired,),
        )
        # The split modules' settings views outlive a state change to uninstalled.
        self._drop_retired_extension_views()

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            self._copy_method_from_button(vals)
            cleaned.append(vals)
        rules = super().create(cleaned)
        if any(rule.method_name for rule in rules):
            self._update_registry()
        return rules

    def write(self, vals):
        vals = dict(vals)
        if vals.get("model_id") and "button_id" not in vals:
            drop = self.filtered(lambda rule: rule.button_id and rule.button_id.model_id.id != vals["model_id"])
            if drop:
                super(ApprovalRule, drop).write({"button_id": False})
        self._copy_method_from_button(vals)
        res = super().write(vals)
        if {"method_name", "model_id", "active"} & set(vals):
            self._update_registry()
        return res

    def unlink(self):
        res = super().unlink()
        self._update_registry()
        return res

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _document_amount(self, record):
        """Document amount converted into the rule currency."""
        self.ensure_one()
        amount, currency = self.env["approval.engine"]._raw_amount(record)
        if currency and currency != self.currency_id:
            company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
            date = False
            for fname in ("date_order", "invoice_date", "date"):
                if fname in record._fields and record[fname]:
                    date = fields.Date.to_date(record[fname])
                    break
            amount = currency._convert(amount, self.currency_id, company, date or fields.Date.context_today(self))
        return amount

    def _applicable_lines(self, record):
        """Stages whose Amount Threshold matches the document.

        Amount is configured only on the stage. A stage set to Always is asked
        for every amount. An inactive role is skipped.
        """
        self.ensure_one()
        amount = self._document_amount(record)
        lines = self.env["approval.rule.line"]
        for line in self.line_ids.sorted(lambda item: (item.sequence, item.id)):
            if not line.role_id.active:
                continue
            if not line._applies(amount):
                continue
            lines |= line
        return lines

    def _matches(self, record, user=None):
        self.ensure_one()
        user = user or self.env.user
        if not self.active or self.model_name != record._name:
            return False
        if self.company_id and "company_id" in record._fields and record.company_id != self.company_id:
            return False
        if self.department_ids and self.env["approval.engine"]._department_wise():
            dept = user.sudo().employee_id.department_id
            allowed = self.env["hr.department"].sudo().search([("id", "child_of", self.department_ids.ids)])
            if not dept or dept not in allowed:
                return False
        domain = ast.literal_eval(self.domain or "[]")
        if domain and not record.sudo().filtered_domain(domain):
            return False
        if self.line_ids and not self.line_ids.filtered(lambda line: line.role_id.active):
            raise ValidationError(_(
                "Rule '%s' has no active role. Activate a role on this rule before the document can continue.",
                self.name,
            ))
        return bool(self._applicable_lines(record))
