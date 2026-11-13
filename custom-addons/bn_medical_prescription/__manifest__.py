{
    'name': 'Medical Prescription Billing',
    'version': '1.0',
    'summary': 'Prescription desk approves the products for a patient, the billing counter bills them',
    'description': """
Flow on Medical & Health POS counters:

1. The patient is registered (Donee + Medical) and sees the doctor.
2. Prescription Desk POS: select the patient, add the prescribed products, Approve.
3. Billing Counter POS: select the patient, the approved products are loaded, take the payment.
""",
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical & Health',
    'depends': [
        'bn_medical_pos',
        'bn_pos_order',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/record_rule.xml',

        'data/sequence.xml',

        'views/medical_prescription.xml',
        'views/pos_config.xml',
        'views/pos_order.xml',
        'views/patient.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_medical_prescription/static/src/app/**/*',
        ],
    },
}
