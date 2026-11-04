from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # attachment size limit (see ir_attachment.py)
    max_file_size = fields.Float('Max File Size (MB)', default=5)
