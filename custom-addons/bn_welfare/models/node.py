from odoo import api, models


class WelfareNode(models.Model):
    _name = 'welfare'
    _inherit = ['welfare', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + []


class WelfareLineNode(models.Model):
    _inherit = 'welfare.line'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']


class WelfareRecurringLineNode(models.Model):
    _inherit = 'welfare.recurring.line'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
