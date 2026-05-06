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
        json.receive_voucher = this.receive_voucher || false;
        json.qurbani = this.qurbani || false;

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

    /**
     * Setter for qurbani
     */
    set_qurbani(qurbani) {
        this.qurbani = qurbani;
    },

    /**
     * Getter for qurbani
     */
    get_qurbani() {
        return this.qurbani;
    },

    /**
     * Setter for receive_voucher
     */
    set_receive_voucher(receive_voucher) {
        this.receive_voucher = receive_voucher;
    },

    /**
     * Getter for qurbani
     */
    get_receive_voucher() {
        return this.receive_voucher;
    },

    /**
     * Setter for pos_cheque_order_id
     */
    set_pos_cheque_order_id(pos_cheque_order_id) {
        this.pos_cheque_order_id = pos_cheque_order_id;
    },

    /**
     * Getter for pos_cheque_order_id
     */
    get_pos_cheque_order_id() {
        return this.pos_cheque_order_id;
    },
});
