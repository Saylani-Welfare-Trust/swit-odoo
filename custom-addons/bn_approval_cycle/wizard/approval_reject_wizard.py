from odoo import _, fields, models


class ApprovalRejectWizard(models.TransientModel):
    _name = "approval.reject.wizard"
    _description = "Reject Approval Request"

    request_id = fields.Many2one("approval.request", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        request = self.request_id
        request._lock()
        request._check_can_decide()
        request.current_stage_id.sudo().write({
            "state": "rejected",
            "decision_user_id": self.env.user.id,
            "decision_date": fields.Datetime.now(),
            "comments": self.reason,
        })
        request.sudo().write({
            "state": "rejected",
            "rejection_reason": self.reason,
            "completed_date": fields.Datetime.now(),
        })
        request._clear_activities()
        request.sudo().message_post(body=_("Rejected by %(user)s. Reason: %(reason)s",
                                           user=self.env.user.display_name, reason=self.reason))
        request._notify_source(_("Approval %(name)s rejected. Reason: %(reason)s",
                                 name=request.name, reason=self.reason))
        return {"type": "ir.actions.act_window_close"}
