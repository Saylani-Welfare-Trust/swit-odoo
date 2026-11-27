# -*- coding: utf-8 -*-
from odoo import models, fields


class MasterRfqAssignee(models.Model):
    """The employees a Purchase Request can be assigned to (its "Assigned To"),
    to create its RFQs."""
    _name = 'master.rfq.assignee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'RFQ Assignee List'
    _rec_name = 'employee_id'
    _order = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        tracking=True,
        domain=[('user_id', '!=', False)],
        help='Only employees linked to a user can be selected, '
             'because they need to log in to create the RFQs.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        related='employee_id.user_id',
        store=True,
        readonly=True,
    )
    work_email = fields.Char(
        'Work Email',
        related='employee_id.work_email',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )

    active = fields.Boolean(default=True, tracking=True)

    _sql_constraints = [
        ('employee_unique', 'UNIQUE(employee_id)', 'This employee is already in the RFQ Assignee List.'),
    ]
