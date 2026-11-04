# -*- coding: utf-8 -*-
from odoo import models, fields


class MasterCxoApprover(models.Model):
    _name = 'master.cxo.approver'
    _description = 'CXO Approver List'
    _rec_name = 'employee_id'
    _order = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        domain=[('user_id', '!=', False)],
        help='Only employees linked to a user can be selected, '
             'because they need to log in to approve.',
    )

    # Related convenience fields, so existing code that reads
    # `designated_cxo_approver_id.user_id` keeps working unchanged.
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

    active = fields.Boolean(default=True)