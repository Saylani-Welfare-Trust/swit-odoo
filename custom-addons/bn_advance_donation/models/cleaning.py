from odoo import models, fields

class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.lines'



    advance_donation_id = fields.Integer(string="Temp Fix")  # 👈 TEMP
    
    
class AdvanceDonationLine(models.Model):
    _name = 'advance.donation'
    
    name = fields.Char(string="Temp Fix")  # 👈 TEMP