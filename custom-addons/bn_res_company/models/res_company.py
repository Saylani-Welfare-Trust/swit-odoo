from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Attachment size limit (see ir_attachment.py and the chatter upload check).
    # The program settings of the company form (POS DN image, Donation API,
    # Welfare API ...) belong to the modules that use them.
    max_file_size = fields.Float('Max File Size (MB)', default=5)
