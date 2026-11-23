{
    'name': 'Medical Prescription Billing',
    'version': '1.5',
    'summary': 'One Medical & Health counter: paid till with a doctor, prescription approved on stock, then its bill',
    'description': """
Flow on a Medical & Health POS counter:

1. Select the patient and the product, Approve, choose the doctor of that product, take the payment: a till is made and a draft prescription is created with the product as its Category.
2. Prescriptions: the doctor or a Medical & Health user adds the products and approves (refused when a product's on hand quantity is 0 or less).
3. Counter: the approved prescription loads for the patient and is billed.
""",
    'author': 'BytesNode',
    'website': 'https://bytesnode.com/',
    'license': 'LGPL-3',
    'category': 'BytesNode/Medical & Health',
    'depends': ['bn_stock_location',
        'bn_master_setup',
        'bn_medical_pos',
        'bn_pos_order',
    ],
    'data': [
        'security/ir.model.access.csv', 'security/analytic_scope_rule.xml',
        'security/record_rule.xml',

        'data/sequence.xml',

        'views/medical_doctor.xml',
        'views/medical_prescription.xml',
        'views/pos_order.xml',
        'views/patient.xml',
        'views/search_filters.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'point_of_sale._assets_pos': [
            'bn_medical_prescription/static/src/app/**/*',
        ],
    },
}
