from odoo import fields, models


class MedicalDoctor(models.Model):
    """Master Setup: the doctors, with the products they are chosen for at the counter"""
    _name = 'medical.doctor'
    _description = 'Doctor'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char('Doctor', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.company)
    product_ids = fields.Many2many(
        'product.product', 'medical_doctor_product_rel', 'doctor_id', 'product_id', 'Products',
        domain="[('available_in_pos', '=', True), ('sale_ok', '=', True)]",
        help="The counter offers this doctor when all the products selected on the order are listed here.")
    user_ids = fields.Many2many(
        'res.users', 'medical_doctor_user_rel', 'doctor_id', 'user_id', 'Users',
        domain="[('share', '=', False)]",
        help="The doctor's login and the staff working with them: they see this doctor's prescriptions, "
             "add the products and approve them. They also need the Medical & Health / User group.")
