# -*- coding: utf-8 -*-
from odoo import api, fields, models, exceptions

class LivestockStock(models.Model):
    _name = 'livestock.stock'
    _description = 'Livestock Stock & Distribution'
    _order = 'monthly_id desc, category'

    monthly_id = fields.Many2one(
        'raw.meat.monthly.requirement',
        string="Monthly Requirement",
        required=True,
        ondelete='cascade',
        help="Link to the consolidated meat requirement record"
    )
    category   = fields.Selection(
        [('goat', 'Goat'), ('cow', 'Cow'), ('buffalo', 'Buffalo')],
        string="Animal Category",
        required=True,
    )
    total_animals = fields.Integer(
        string="Total Animals Allocated",
        compute='_compute_total_from_branch',
        store=True,
        help="Sum of branch confirmations for this category"
    )
    distributed_animals = fields.Integer(
        string="Animals Distributed",
        default=0,
        help="Count of animals already distributed"
    )
    available_animals = fields.Integer(
        string="Available for Distribution",
        compute='_compute_available',
        store=True,
        help="total_animals − distributed_animals"
    )
   


    @api.depends('monthly_id.branch_livestock_ids.quantity')
    def _compute_total_from_branch(self):
        """Sum all branch livestock confirmations of this category."""
        for rec in self:
            lines = rec.monthly_id.branch_livestock_ids.filtered(
                lambda l: l.category == rec.category
            )
            rec.total_animals = sum(lines.mapped('quantity'))

    @api.depends('total_animals', 'distributed_animals')
    def _compute_available(self):
        for rec in self:
            rec.available_animals = rec.total_animals - rec.distributed_animals

    @api.constrains('distributed_animals')
    def _check_distribution(self):
        for rec in self:
            if rec.distributed_animals > rec.total_animals:
                raise exceptions.ValidationError(
                    "You cannot distribute more animals (%d) than allocated (%d)."
                    % (rec.distributed_animals, rec.total_animals)
                )
