{
    "name": "Saylani ERP Go Live Banner",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "summary": "Custom ERP Dashboard Banner for Saylani ERP",

    "license": "LGPL-3",

    "depends": [
        "web",
    ],

    "assets": {
        "web.assets_backend": [
            "saylani_erp_banner/static/src/js/banner.js",
            "saylani_erp_banner/static/src/css/banner.css",
        ],
    },

    "installable": True,
    "application": False,
    "auto_install": False,
}
