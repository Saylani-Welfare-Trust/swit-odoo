from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _approval_department_ids(self):
        self.ensure_one()
        return self.employee_ids.department_id.ids

    def _approval_department_wise(self):
        return self.env["ir.config_parameter"].sudo().get_param("approval_cycle.department_wise") == "True"

    def _approval_request_domain(self):
        """Requests this user may see.

        With department-wise approval, that is their department's requests.
        They still see a request they raised or must approve, so a CFO outside
        the department can decide it. With the switch off, colleagues do not
        see the rest of the department.
        """
        self.ensure_one()
        own_or_assigned = [
            "|",
            ("requester_id", "=", self.id),
            ("stage_ids.approver_ids", "in", [self.id]),
        ]
        department_ids = self._approval_department_ids() if self._approval_department_wise() else []
        if not department_ids:
            return own_or_assigned
        return [
            "|",
            ("department_id", "in", department_ids),
            *own_or_assigned,
        ]

    def _approval_request_stage_domain(self):
        """Stages of the requests this user may see."""
        self.ensure_one()
        own_or_assigned = [
            "|",
            ("request_id.requester_id", "=", self.id),
            ("request_id.stage_ids.approver_ids", "in", [self.id]),
        ]
        department_ids = self._approval_department_ids() if self._approval_department_wise() else []
        if not department_ids:
            return own_or_assigned
        return [
            "|",
            ("request_id.department_id", "in", department_ids),
            *own_or_assigned,
        ]
