from odoo import api, fields, models


class SadqaJariyaNode(models.Model):
    _name = 'sadqa.jariya'
    _inherit = ['sadqa.jariya', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + []


class SadqaJariyaLineNode(models.Model):
    _inherit = 'sadqa.jariya.line'
    # Branch picker: only the user's branches (Branch / Site Access: their Branches / Sites)
    analytic_account_id = fields.Many2one(context={'branch_scope': True})

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']


class SadqaJariyaRecurringLineNode(models.Model):
    _inherit = 'sadqa.jariya.recurring.line'
    # Branch picker: only the user's branches (Branch / Site Access: their Branches / Sites)
    analytic_account_id = fields.Many2one(context={'branch_scope': True})

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
