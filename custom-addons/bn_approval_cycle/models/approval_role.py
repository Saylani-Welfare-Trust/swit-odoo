from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ApprovalRole(models.Model):
    _name = "approval.role"
    _description = "Approval Role"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    approver_type = fields.Selection(
        [("users", "Specific Users"), ("group", "Security Group"),
         ("department_manager", "Requester's Department Manager")],
        required=True,
        default="users",
        tracking=True,
    )
    escalate_to_parents = fields.Boolean(
        string="Include Parent Department Managers",
        default=True,
        tracking=True,
        help="After the requester's own department manager, also require each parent "
             "department's manager. A level is skipped when it has no manager, or when "
             "that manager is the same person as a lower level. Turn this off to ask "
             "only the nearest manager.",
    )
    user_ids = fields.Many2many(
        "res.users", "approval_role_user_rel", "role_id", "user_id", string="Approvers",
        tracking=True,
    )
    group_id = fields.Many2one("res.groups", string="Approver Group", tracking=True)
    same_department_only = fields.Boolean(
        string="Requester's Department Only",
        tracking=True,
        help="Only approvers who work in the requester's department (or its sub-departments) are eligible.",
    )
    description = fields.Text(tracking=True)
    department_wise_enabled = fields.Boolean(compute="_compute_department_wise_enabled")

    def _compute_department_wise_enabled(self):
        enabled = self.env["approval.engine"]._department_wise()
        for rec in self:
            rec.department_wise_enabled = enabled

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        tracking=True,
        help="Leave empty to make the role available to all companies.",
    )

    _sql_constraints = [
        ("approval_role_code_uniq", "unique(code)", "Approval role code must be unique."),
    ]

    @api.constrains("active", "approver_type", "user_ids", "group_id")
    def _check_approver_configuration(self):
        # Starter roles are inactive until an administrator configures them.
        for role in self.filtered("active"):
            if role.approver_type == "users" and not role.user_ids:
                raise ValidationError(_("Select at least one approver for active role '%s'.", role.name))
            if role.approver_type == "group" and not role.group_id:
                raise ValidationError(_("Select an approver group for active role '%s'.", role.name))

    def _resolve_approvers(self, company, department=False):
        """Active internal users of this role who may act in ``company`` for a request
        raised from ``department`` (an ``hr.department`` record or empty)."""
        self.ensure_one()
        if self.company_id and company and self.company_id != company:
            return self.env["res.users"]
        if self.approver_type == "users":
            users = self.user_ids
        elif self.approver_type == "group" and self.group_id:
            users = self.group_id.sudo().users
        else:
            return self.env["res.users"]
        if self.same_department_only and self.approver_type != "department_manager":
            if not department:
                return self.env["res.users"]
            dept_ids = self.env["hr.department"].sudo().search([("id", "child_of", department.id)]).ids
            users = users.filtered(
                lambda u: u.sudo().employee_ids.department_id.ids and set(u.sudo().employee_ids.department_id.ids) & set(dept_ids)
            )
        return users.filtered(
            lambda u: u.active and not u.share and (not company or company in u.company_ids)
        )
