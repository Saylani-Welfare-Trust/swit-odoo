from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _check_file_size(self, file_size):
        """
        Check if the file size is within the limit set in company settings.
        """
        max_size_mb = self.env.company.max_file_size

        # if no limit is set, allow all sizes
        if not max_size_mb:
            return True
        
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False
        return True


    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        attachments._check_attachment_size()
        return attachments


    def _check_attachment_size(self):
        """
        Check attachment size against company limit.
        """
        for attachment in self:
            
            # Skip non-binary or empty
            if not attachment.datas or attachment.type != "binary":
                continue

            # Skip system / internal attachments
            if not attachment.res_model or attachment.res_model.startswith("ir."):
                continue

            # Skip system-generated users
            if not attachment.create_uid:
                continue

            # getting file size
            if attachment.file_size:
                file_size = attachment.file_size
            else:
                file_size = len(base64.b64decode(attachment.datas))


            # checking file size
            check = self._check_file_size(file_size)
            if check:
                continue

            raise ValidationError(
                _("File exceeds the maximum allowed size of %s MB.") % self.env.company.max_file_size
            )

