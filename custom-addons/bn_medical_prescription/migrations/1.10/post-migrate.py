from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """The prescription numbers restart every day: RX/26112026/0001.
    The sequence is a noupdate record, so the new format in data/sequence.xml only reaches new databases.
    The numbers already given stay as they are."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    sequence = env.ref('bn_medical_prescription.seq_medical_prescription', raise_if_not_found=False)
    if sequence:
        sequence.write({
            'prefix': 'RX/%(range_day)s%(range_month)s%(range_year)s/',
            'padding': 4,
            'use_date_range': True,
        })
