/** @odoo-module **/
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    /**
     * Override export_as_JSON to include custom fields like CNIC and source_document
     */
    export_as_JSON() {
        // Get the original JSON
        const json = super.export_as_JSON(...arguments);

        // Include source_document if set
        json.source_document = this.source_document || false;

        return json;
    },

    /**
     * Setter for source_document
     */
    set_source_document(source_document) {
        this.source_document = source_document;
    },

    /**
     * Getter for source_document
     */
    get_source_document() {
        return this.source_document;
    },
});
