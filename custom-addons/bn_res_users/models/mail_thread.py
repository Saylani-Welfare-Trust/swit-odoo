from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_compute_author(self, author_id=None, email_from=None, raise_on_email=True):
        """Staff accounts often have no email address. Odoo refuses every
        chatter post of such a user ("Unable to send message, please configure
        the sender's email address"), which blocks the workflow buttons that
        log their step. Let internal users post without one; emails sent for
        the message fall back to the default sender address."""
        if raise_on_email and self.env.user._is_internal():
            raise_on_email = False
        return super()._message_compute_author(author_id, email_from, raise_on_email=raise_on_email)
