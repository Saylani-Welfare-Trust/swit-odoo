from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

TODO_ACTIVITY = "mail.mail_activity_data_todo"


class ApprovalRequest(models.Model):
    _name = "approval.request"
    _description = "Approval Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _mail_post_access = "read"

    name = fields.Char(required=True, copy=False, default=lambda self: _("New"), tracking=True)
    rule_id = fields.Many2one("approval.rule", required=True, ondelete="restrict", tracking=True)
    previous_request_id = fields.Many2one(
        "approval.request", string="Previous Request", readonly=True, copy=False,
        tracking=True,
        help="The request for the previous stage of the same document.",
    )
    method_name = fields.Char(string="Button Method", readonly=True, index=True, tracking=True)
    model_name = fields.Char(required=True, index=True, tracking=True)
    res_id = fields.Integer(required=True, index=True)
    document_name = fields.Char(readonly=True, tracking=True)
    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    department_id = fields.Many2one(
        "hr.department", string="Department", readonly=True, index=True,
        tracking=True,
        help="Department of the requester when the request was raised.",
    )
    approval_department_id = fields.Many2one(
        "hr.department", string="Approving Department", readonly=True, index=True, tracking=True,
        help="Department whose manager must approve this step. Empty for roles such as CFO or Internal Audit.",
    )
    department_wise_enabled = fields.Boolean(compute="_compute_department_wise_enabled")
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")],
        default="pending", required=True, tracking=True, index=True,
    )
    executed = fields.Boolean(
        readonly=True, copy=False, tracking=True,
        help="Set once the approved business operation has been completed.",
    )
    current_stage_id = fields.Many2one("approval.request.stage", tracking=True)
    stage_ids = fields.One2many("approval.request.stage", "request_id", string="Approval History")
    rejection_reason = fields.Text(tracking=True)
    requested_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    completed_date = fields.Datetime(readonly=True, tracking=True)
    amount = fields.Monetary(currency_field="currency_id", readonly=True, tracking=True)
    currency_id = fields.Many2one("res.currency", readonly=True, tracking=True)
    can_decide = fields.Boolean(compute="_compute_can_decide")

    _sql_constraints = [
        ("approval_request_res_id_check", "CHECK(res_id > 0)",
         "Approval request must reference a valid record ID."),
    ]

    @api.depends("state", "current_stage_id.approver_ids", "current_stage_id.approved_user_ids",
                 "current_stage_id.allow_requester", "requester_id")
    @api.depends_context("uid")
    def _compute_can_decide(self):
        user = self.env.user
        for rec in self:
            stage = rec.current_stage_id
            rec.can_decide = bool(
                rec.state == "pending" and stage and user in stage.approver_ids
                and user not in stage.approved_user_ids
                and (stage.allow_requester or rec.requester_id != user)
            )

    def _compute_department_wise_enabled(self):
        enabled = self.env["approval.engine"]._department_wise()
        for rec in self:
            rec.department_wise_enabled = enabled

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("approval.request") or _("Approval")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _lock(self):
        """Serialise concurrent decisions on the same requests."""
        self.env.cr.execute("SELECT id FROM approval_request WHERE id IN %s FOR UPDATE", (tuple(self.ids),))
        self.invalidate_recordset()

    def _notify_source(self, body):
        record = self.env[self.model_name].sudo().browse(self.res_id).exists() if self.model_name in self.env else False
        if record and hasattr(record, "message_post"):
            record.message_post(body=body)

    def _clear_activities(self):
        self.sudo().activity_unlink([TODO_ACTIVITY])

    def _document_changed(self):
        """True if the document amount/currency differs from the approved snapshot."""
        self.ensure_one()
        record = self.env[self.model_name].sudo().browse(self.res_id).exists()
        if not record:
            return True
        amount, currency = self.env["approval.engine"]._raw_amount(record)
        return currency != self.currency_id or self.currency_id.compare_amounts(amount, self.amount) != 0

    def action_open_document(self):
        self.ensure_one()
        if self.model_name not in self.env:
            raise UserError(_("The target model no longer exists."))
        Model = self.env[self.model_name]
        record = Model.sudo().browse(self.res_id).exists()
        if not record:
            raise UserError(_("The target document no longer exists."))
        as_user = record.with_user(self.env.user)
        if not as_user.check_access_rights("read", raise_exception=False) or not self._can_read(as_user):
            raise UserError(_(
                "You cannot open %(document)s. Your user needs read access on %(model)s.",
                document=self.document_name or record.display_name,
                model=Model._description,
            ))
        return {
            "type": "ir.actions.act_window",
            "name": self.document_name or record.display_name,
            "res_model": self.model_name,
            "res_id": self.res_id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    @staticmethod
    def _can_read(record):
        try:
            record.check_access_rule("read")
        except AccessError:
            return False
        return True

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------
    def _check_can_decide(self):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("This approval request is no longer pending."))
        stage = self.current_stage_id
        if not stage:
            raise UserError(_("There is no active approval stage."))
        if self.env.user not in stage.approver_ids:
            raise AccessError(_("You are not an assigned approver for the current stage."))
        if not stage.allow_requester and self.requester_id == self.env.user:
            raise AccessError(_("The requester cannot approve their own request at this stage."))
        if self._document_changed():
            raise UserError(_(
                "The document was modified after this request was created. "
                "Cancel this request and submit the document again."))

    def action_approve(self):
        self._lock()
        result = True
        for request in self:
            request._check_can_decide()
            stage = request.current_stage_id
            if self.env.user in stage.approved_user_ids:
                raise UserError(_("You have already approved this stage."))
            stage.sudo().write({"approved_user_ids": [(4, self.env.user.id)]})
            approvals = len(stage.approved_user_ids)
            if approvals < stage.required_approvals:
                request.sudo().message_post(body=_(
                    "%(user)s approved stage '%(role)s' (%(done)s of %(required)s approvals received).",
                    user=self.env.user.display_name, role=stage.role_id.display_name,
                    done=approvals, required=stage.required_approvals))
                continue
            stage.sudo().write({
                "state": "approved",
                "decision_user_id": self.env.user.id,
                "decision_date": fields.Datetime.now(),
            })
            request._clear_activities()
            next_request = request._spawn_next_request()
            if next_request:
                request.sudo().write({
                    "state": "approved",
                    "executed": True,
                    "completed_date": fields.Datetime.now(),
                })
                request.sudo().message_post(body=_(
                    "Stage '%(role)s' approved by %(user)s. Next request: %(next)s.",
                    role=stage.role_id.display_name, user=self.env.user.display_name,
                    next=next_request.display_name))
                request._notify_source(_(
                    "Approval %(current)s granted. Next approval is %(next)s.",
                    current=request.name, next=next_request.name))
                continue
            completed = request._complete_approval()
            if isinstance(completed, dict):
                result = completed
        return result

    def _spawn_next_request(self):
        """Create the request for the next rule stage, or an empty recordset."""
        self.ensure_one()
        # The approver may not have access to the source document.
        record = self.env[self.model_name].sudo().browse(self.res_id).exists()
        if not record:
            raise UserError(_("The target document no longer exists."))
        engine = self.env["approval.engine"]
        department_wise = engine._department_wise()
        department = self.department_id or (
            self.requester_id.sudo().employee_id.department_id if department_wise else self.env["hr.department"])
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        steps = engine._approval_steps(
            record, self.rule_id, self.requester_id, department, company, department_wise)
        current_line = self.stage_ids.rule_line_id[:1]
        current_dept = self.approval_department_id.id or False
        index = None
        for position, step in enumerate(steps):
            dept = step["approval_department"]
            dept_id = dept.id if dept else False
            if step["line"] == current_line and dept_id == current_dept:
                index = position
                break
        if index is None or index + 1 >= len(steps):
            return self.env["approval.request"]
        return engine._create_request(
            record, self.rule_id, requester=self.requester_id, previous=self, step=steps[index + 1],
        )

    def action_reject(self):
        self.ensure_one()
        self._check_can_decide()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Approval"),
            "res_model": "approval.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_cancel(self):
        self._lock()
        is_manager = self.env.user.has_group("bn_approval_cycle.group_approval_manager")
        for request in self:
            if request.state != "pending":
                raise UserError(_("Only pending requests can be cancelled."))
            if request.requester_id != self.env.user and not is_manager:
                raise AccessError(_("Only the requester or an approval manager can cancel this request."))
            request._cancel_internal(_("Cancelled by %s.", self.env.user.display_name))
        return True

    def _cancel_internal(self, message):
        for request in self:
            request.sudo().write({"state": "cancelled", "completed_date": fields.Datetime.now()})
            request.stage_ids.filtered(lambda s: s.state == "pending").sudo().write({"state": "cancelled"})
            request._clear_activities()
            request.sudo().message_post(body=message)

    def _complete_approval(self):
        """Run the protected operation. It executes in the same transaction, so a
        failure rolls the approval back instead of reporting a false success."""
        self.ensure_one()
        record = self.env[self.model_name].sudo().browse(self.res_id).exists()
        if not record:
            raise UserError(_("The target document no longer exists."))
        method = self.method_name or self.rule_id.method_name
        if not method or not callable(getattr(record, method, None)):
            raise ValidationError(_(
                "The button %(method)s is no longer available on %(model)s.",
                method=method or "-", model=self.model_name,
            ))
        self.sudo().write({"state": "approved", "completed_date": fields.Datetime.now()})
        self._clear_activities()
        self.sudo().message_post(body=_("Final approval reached. Running %s.", method))
        self._notify_source(_("Approval %(name)s completed. %(method)s was run on this document.",
                              name=self.name, method=method))
        # The button runs with the requester's rights. The gate lets it through
        # because this approved request exists and has not been executed yet.
        runner = self.requester_id if self.requester_id.active else self.env.user
        return getattr(record.with_user(runner).with_company(self.company_id), method)()

    def action_resubmit(self):
        self.ensure_one()
        if self.state not in ("rejected", "cancelled"):
            raise UserError(_("Only rejected or cancelled requests can be resubmitted."))
        if self.requester_id != self.env.user and not self.env.user.has_group("bn_approval_cycle.group_approval_manager"):
            raise AccessError(_("Only the requester or an approval manager can resubmit this request."))
        if self.model_name not in self.env:
            raise UserError(_("The target model no longer exists."))
        record = self.env[self.model_name].sudo().browse(self.res_id).exists()
        if not record:
            raise UserError(_("The target document no longer exists."))
        engine = self.env["approval.engine"]
        rule = engine._find_rule(record, self.method_name, user=self.requester_id)
        if not rule:
            raise UserError(_("No active approval rule applies to this document any more."))
        new_request = engine._create_request(record, rule, requester=self.requester_id)
        return {
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "res_id": new_request.id,
            "view_mode": "form",
            "target": "current",
        }
