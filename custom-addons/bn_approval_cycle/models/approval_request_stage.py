from odoo import _, api, fields, models

from .approval_request import TODO_ACTIVITY


class ApprovalRequestStage(models.Model):
    _name = "approval.request.stage"
    _description = "Approval Request Stage"
    _order = "sequence, id"
    _rec_names_search = ["role_id", "request_id"]

    request_id = fields.Many2one("approval.request", required=True, ondelete="cascade", index=True)
    rule_line_id = fields.Many2one(
        "approval.rule.line", string="Configured Stage", ondelete="set null", index=True,
    )
    sequence = fields.Integer(required=True)
    role_id = fields.Many2one("approval.role", required=True, ondelete="restrict")
    approver_ids = fields.Many2many(
        "res.users", "approval_request_stage_user_rel", "stage_id", "user_id",
        string="Assigned Approvers", readonly=True,
    )
    approved_user_ids = fields.Many2many(
        "res.users", "approval_request_stage_approved_user_rel", "stage_id", "user_id",
        string="Approvers Who Approved", readonly=True,
    )
    required_approvals = fields.Integer(default=1, required=True)
    allow_requester = fields.Boolean(default=False)
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"),
         ("rejected", "Rejected"), ("cancelled", "Cancelled")],
        default="pending", required=True,
    )
    decision_user_id = fields.Many2one("res.users", readonly=True)
    decision_date = fields.Datetime(readonly=True)
    comments = fields.Text()

    @api.depends("role_id.name", "state", "request_id.name")
    def _compute_display_name(self):
        labels = dict(self._fields["state"]._description_selection(self.env))
        for stage in self:
            role = stage.role_id.name or _("Stage")
            state = labels.get(stage.state)
            stage.display_name = "%s — %s" % (role, state) if state else role

    def init(self):
        # Older requests kept later stages as "waiting" on the same record.
        # The flow now creates a new request for the next stage.
        self.env.cr.execute(
            "UPDATE approval_request_stage SET state = 'pending' WHERE state = 'waiting'"
        )

    def _schedule_activities(self):
        for stage in self:
            request = stage.request_id.sudo()
            for user in stage.approver_ids:
                request.activity_schedule(
                    TODO_ACTIVITY,
                    user_id=user.id,
                    summary=_("Approval required: %s", stage.role_id.name),
                    note=_("Please review approval request %s.", request.display_name),
                )
