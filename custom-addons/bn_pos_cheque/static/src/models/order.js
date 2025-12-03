/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    export_for_printing() {
        return {
            ...super.export_for_printing(),
            
            bank_name: this.bank_name,
            cheque_number: this.cheque_number,
            cheque_date: this.cheque_date,
            qr_code: this.qr_code,
        };
    },

    set_bank_name(bank_name){
        this.bank_name = bank_name
    },

    set_cheque_number(cheque_number){
        this.cheque_number = cheque_number
    },
    
    set_cheque_date(cheque_date){
        this.cheque_date = cheque_date
    },
    
    set_qr_code(qr_code){
        this.qr_code = qr_code
    },

    get_bank_name(){
        return this.bank_name
    },
    
    get_cheque_number(){
        return this.cheque_number
    },
    
    get_cheque_date(){
        return this.cheque_date
    },
    
    get_qr_code(){
        return this.cheque_date
    }
});
