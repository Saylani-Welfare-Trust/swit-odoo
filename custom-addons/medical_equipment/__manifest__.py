
{
	"name"         : "Medical Equipment",
	"category"     : "Medical Equipment",
	"version"      : "1.0.0",
	"sequence"     : 1,
	"website"      : "",
    "depends"              :  ['web','base','point_of_sale','product','account','base_account_budget','point_of_sale'],
	"data"         : [
        "views/product_view.xml",
	],
	'assets': {
        'point_of_sale._assets_pos': [
			'medical_equipment/static/src/xml/medical_equipment_btn.xml',
			'medical_equipment/static/src/js/medical_equipment_btn.js',
            
			'medical_equipment/static/src/xml/medical_screen.xml',
            'medical_equipment/static/src/js/medical_screen.js',
            		
			
	    ]
    },


	"installable"  : True,
}
