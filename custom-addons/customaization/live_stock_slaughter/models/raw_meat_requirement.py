# -*- coding: utf-8 -*-
from odoo import api, fields, models, exceptions
from datetime import date, timedelta, datetime


class RawMeatKitchenRequest(models.Model):
    _name = 'raw.meat.kitchen.request'
    _description = 'Kitchen Department Meat Request'

    date = fields.Date( default=fields.Date.context_today)
    quantity = fields.Float(string="Quantity (kg)", required=True)
    monthly_id = fields.Many2one(
        'raw.meat.monthly.requirement',
        string="Monthly Requirement",
        ondelete='cascade',
    )


class RawMeatMadarisApproval(models.Model):
    _name = 'raw.meat.madaris.approval'
    _description = 'Madaris/Masajid Raw Meat Approval'

    date = fields.Date( default=fields.Date.context_today)
    quantity = fields.Float(string="Approved Quantity (kg)", required=True)
    monthly_id = fields.Many2one(
        'raw.meat.monthly.requirement',
        string="Monthly Requirement",
        ondelete='cascade',
    )


class RawMeatMedicalReferral(models.Model):
    _name = 'raw.meat.medical.referral'
    _description = 'Medical Department Referred Cases'

    date = fields.Date( default=fields.Date.context_today)
    quantity = fields.Float(string="Approx. Quantity (kg)", required=True)
    monthly_id = fields.Many2one(
        'raw.meat.monthly.requirement',
        string="Monthly Requirement",
        ondelete='cascade',
    )


class BranchLivestockConfirmation(models.Model):
    _name = 'branch.livestock.confirmation'
    _description = 'Branch Livestock Confirmation for Slaughter'

    branch_id = fields.Many2one('res.company', default=lambda self: self.env.company.id,
                                required=True)
    category = fields.Selection(
        [('goat', 'Goat'), ('cow', 'Cow'), ('buffalo', 'Buffalo')],
        
    )

    date = fields.Date(
        string='Date',
        required=False)

    product_id = fields.Many2one(
        'product.product', string='Livestock',

    )

    quantity = fields.Float(
        string='Quantity',
        required=False)
    branch_name = fields.Many2one(
        comodel_name='res.company',
        string='Branch Name',
        required=False)
    monthly_id = fields.Many2one(
        'raw.meat.monthly.requirement',
        string="Monthly Requirement",
        ondelete='cascade',
    )


class RawMeatMonthlyRequirement(models.Model):
    _name = 'raw.meat.monthly.requirement'
    _description = 'Consolidated Monthly Meat & Livestock Requirement'
    _order = 'month desc'

    name = fields.Char(
        compute='_compute_name',
        store=True
    )

    MONTHS = [
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    # store as string keys '1'..'12'; default to current month
    month = fields.Selection(
        selection=MONTHS,
        string='Month',
        
    )
    # month                    = fields.Date(
    #     string="For Month",
    #     
    #     help="Must be set by 22nd of previous month"
    # )
    kitchen_request_ids = fields.One2many(
        'raw.meat.kitchen.request', 'monthly_id',
        string="Kitchen Requests"
    )
    madaris_approval_ids = fields.One2many(
        'raw.meat.madaris.approval', 'monthly_id',
        string="Madaris/Masajid Approvals"
    )
    medical_referral_ids = fields.One2many(
        'raw.meat.medical.referral', 'monthly_id',
        string="Medical Referrals"
    )
    branch_livestock_ids = fields.One2many(
        'branch.livestock.confirmation', 'monthly_id',
        string="Branch Livestock Confirmations"
    )
    total_raw_meat_qty = fields.Float(
        compute='_compute_totals',
        string="Total Raw Meat Required (kg)",
        store=True
    )
    total_livestock_qty = fields.Integer(
        compute='_compute_totals',
        string="Total Livestock Confirmed",
        store=True
    )
    excess_livestock_qty = fields.Integer(
        compute='_compute_totals',
        string="Excess Livestock",
        store=True
    )

    @api.depends('month')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.month

    @api.depends(
        'kitchen_request_ids.quantity',
        'madaris_approval_ids.quantity',
        'medical_referral_ids.quantity',
        'branch_livestock_ids.quantity'
    )
    def _compute_totals(self):
        for rec in self:
            meat_from_kitchen = sum(r.quantity for r in rec.kitchen_request_ids)
            meat_from_madaris = sum(r.quantity for r in rec.madaris_approval_ids)
            meat_from_medical = sum(r.quantity for r in rec.medical_referral_ids)
            rec.total_raw_meat_qty = meat_from_kitchen + meat_from_madaris + meat_from_medical
            rec.total_livestock_qty = sum(r.quantity for r in rec.branch_livestock_ids)
            rec.excess_livestock_qty = max(rec.total_livestock_qty - (rec.total_raw_meat_qty / 5), 0)
            # assuming 1 animal ≈ 5kg of raw meat; adjust conversion as needed

    # @api.constrains('total_raw_meat_qty', 'total_livestock_qty')
    # def _check_match(self):
    #     for rec in self:
    #         # enforce raw meat ≈ livestock * conversion; here exact match
    #         if rec.total_raw_meat_qty and rec.total_livestock_qty:
    #             expected = rec.total_livestock_qty * 5
    #             if abs(rec.total_raw_meat_qty - expected) > 0.001:
    #                 raise exceptions.ValidationError(
    #                     "Raw‑meat total (%.2f kg) does not match "
    #                     "livestock (×5 kg = %.2f kg)." %
    #                     (rec.total_raw_meat_qty, expected)
    #                 )

    @api.model
    def create(self, vals):
        """
        Ensure that a requirement for month M can only be created
        on or before the 22nd of the month immediately before M.
        """
        # Extract the selected month number (1–12)
        try:
            m_num = int(vals.get('month'))
        except (TypeError, ValueError):
            raise exceptions.UserError("Invalid month selection.")

        # Determine the calendar year of month M.
        # If M is January (1) but today is December, assume next year.
        today = fields.Date.context_today(self)
        year = today.year
        if m_num == 1 and today.month == 12:
            year += 1

        # First day of month M in that year
        first_of_m = date(year, m_num, 1)
        # Last day of the preceding month
        last_of_prev = first_of_m - timedelta(days=1)
        # Cut‑off is the 22nd of that preceding month
        cutoff = last_of_prev.replace(day=22)

        if today > cutoff:
            raise exceptions.UserError(
                "You must create the requirement for %s on or before %s."
                % (
                    first_of_m.strftime("%B %Y"),
                    cutoff.strftime("%B %d, %Y"),
                )
            )

        return super(RawMeatMonthlyRequirement, self).create(vals)
