/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    // This sends data to the backend when order is validated
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        
        json.source_document = this.source_document || false;
        
        return json;
    },

    set_source_document(source_document){
        this.source_document = source_document
    },

    get_source_document(){
        return this.source_document
    }
});
