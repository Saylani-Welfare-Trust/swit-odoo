from odoo import api, models


class SadqaJariyaNode(models.Model):
    _name = 'sadqa.jariya'
    _inherit = ['sadqa.jariya', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return super()._node_sources() + []


class SadqaJariyaLineNode(models.Model):
    _inherit = 'sadqa.jariya.line'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']


class SadqaJariyaRecurringLineNode(models.Model):
    _inherit = 'sadqa.jariya.recurring.line'

    @api.model
    def _node_sources(self):
        return super()._node_sources() + ['analytic_account_id']
