from odoo import api, fields, models


class WelfareNode(models.Model):
    _name = 'welfare'
    _inherit = ['welfare', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + []


class WelfareLineNode(models.Model):
    _inherit = 'welfare.line'
    # Branch picker: only the user's branches (Branch / Site Access: their Branches / Sites)
    analytic_account_id = fields.Many2one(context={'branch_scope': True})

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']


class WelfareRecurringLineNode(models.Model):
    _inherit = 'welfare.recurring.line'
    # Branch picker: only the user's branches (Branch / Site Access: their Branches / Sites)
    analytic_account_id = fields.Many2one(context={'branch_scope': True})

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
