from odoo import models, fields, _
from odoo.exceptions import UserError


class SadqaJariyaDisbursementPopupMixin(models.AbstractModel):
    """Assigned Officer (Marfat) marks a line done (with media) or pending"""
    _name = 'sadqa.jariya.disbursement.popup.mixin'
    _description = 'Sadqa e Jariya Disbursement Popup'
    _line_field = None

    donee_id = fields.Many2one('res.partner', string='Donee', readonly=True)
    donee_cnic_no = fields.Char(string='CNIC', related='donee_id.cnic_no')
    donee_mobile = fields.Char(string='Mobile', related='donee_id.mobile')
    donee_street = fields.Char(string='Street', related='donee_id.street')
    donee_street2 = fields.Char(string='Street 2', related='donee_id.street2')
    donee_city = fields.Char(string='City', related='donee_id.city')
    donee_state_id = fields.Many2one('res.country.state', string='State', related='donee_id.state_id')
    donee_country_id = fields.Many2one('res.country', string='Country', related='donee_id.country_id')

    def _line(self):
        return self[self._line_field]

    def _reopen_wizard_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_mark_pending(self):
        self._line().write({
            'media_ids': [(6, 0, self.media_ids.ids)],
            'state': 'pending',
        })
        return self._reopen_wizard_action()

    def action_disbursed(self):
        if not self.media_ids:
            raise UserError(_(
                "Please upload at least one image or video in the Media field "
                "before marking this line as Done."
            ))
        self._line().write({
            'media_ids': [(6, 0, self.media_ids.ids)],
            'state': 'disbursed',
        })
        return self._reopen_wizard_action()


class SadqaJariyaLineDisbursementPopup(models.TransientModel):
    _name = 'sadqa.jariya.line.disbursement.popup'
    _inherit = 'sadqa.jariya.disbursement.popup.mixin'
    _description = 'Sadqa e Jariya Line Disbursement Popup'
    _line_field = 'line_id'

    line_id = fields.Many2one('sadqa.jariya.line', string='Disbursement Line', required=True)
    donee_id = fields.Many2one(related='line_id.donee_id')
    application_id = fields.Many2one(related='line_id.application_id')
    disbursement_category_id = fields.Many2one(related='line_id.disbursement_category_id')
    application_type_id = fields.Many2one(related='line_id.application_type_id')
    product_id = fields.Many2one(related='line_id.product_id')
    quantity = fields.Float(related='line_id.quantity')
    total_amount = fields.Float(related='line_id.total_amount')
    collection_point = fields.Selection(related='line_id.collection_point')
    collection_date = fields.Date(related='line_id.collection_date')
    assigned_officer_id = fields.Many2one(related='line_id.assigned_officer_id')
    state = fields.Selection(related='line_id.state')
    media_ids = fields.Many2many(
        'ir.attachment',
        'sadqa_jariya_line_popup_media_rel',
        'popup_id',
        'attachment_id',
        string='Media (Images/Videos)',
    )


class SadqaJariyaRecurringLineDisbursementPopup(models.TransientModel):
    _name = 'sadqa.jariya.recurring.line.disbursement.popup'
    _inherit = 'sadqa.jariya.disbursement.popup.mixin'
    _description = 'Sadqa e Jariya Recurring Line Disbursement Popup'
    _line_field = 'recurring_line_id'

    recurring_line_id = fields.Many2one('sadqa.jariya.recurring.line', string='Recurring Line', required=True)
    donee_id = fields.Many2one(related='recurring_line_id.donee_id')
    application_id = fields.Many2one(related='recurring_line_id.application_id')
    disbursement_category_id = fields.Many2one(related='recurring_line_id.disbursement_category_id')
    application_type_id = fields.Many2one(related='recurring_line_id.application_type_id')
    product_id = fields.Many2one(related='recurring_line_id.product_id')
    currency_id = fields.Many2one(related='recurring_line_id.currency_id')
    quantity = fields.Float(related='recurring_line_id.quantity')
    amount = fields.Monetary(related='recurring_line_id.amount', currency_field='currency_id')
    collection_point = fields.Selection(related='recurring_line_id.collection_point')
    collection_date = fields.Date(related='recurring_line_id.collection_date')
    assigned_officer_id = fields.Many2one(related='recurring_line_id.assigned_officer_id')
    state = fields.Selection(related='recurring_line_id.state')
    media_ids = fields.Many2many(
        'ir.attachment',
        'sadqa_jariya_recurring_line_popup_media_rel',
        'popup_id',
        'attachment_id',
        string='Media (Images/Videos)',
    )
