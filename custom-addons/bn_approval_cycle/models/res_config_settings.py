from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    approval_enabled = fields.Boolean(
        string="Enable Approval Cycle",
        config_parameter="approval_cycle.enabled",
    )

    approval_department_wise = fields.Boolean(
        string="Department-wise Approval",
        config_parameter="approval_cycle.department_wise",
    )

    def set_values(self):
        super().set_values()
        manager_group = self.env.ref("bn_approval_cycle.group_approval_manager")
        user_group = self.env.ref("bn_approval_cycle.group_approval_user")
        if self.approval_enabled:
            # ERP administrators manage approval roles/rules; internal users can see their own requests.
            manager_group.sudo().write({"users": [(4, u.id) for u in self.env.ref("base.group_erp_manager").users]})
            user_group.sudo().write({"users": [(4, u.id) for u in self.env.ref("base.group_user").users]})
        # Record rules cache the visibility domain. Clearing it makes the
        # department switch take effect on the next search.
        self.env.registry.clear_cache()
