/** @odoo-module **/

import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";
import { patch } from "@web/core/utils/patch";

patch(ProductsWidget.prototype, {

    setup(){
        super.setup(...arguments);
        console.log("partner")
    },
    get currentOrder() {
        console.log(this.pos.get_order());
        
        return this.pos.get_order();
    },
    get is_donee(){
        const partner = this.currentOrder.get_partner();

        if (partner){
            return partner.is_donee
        }
        return false
    },
    setOrderType(e){    
        // console.log(e.target.value)
        this.currentOrder.set_order_type(e.target.value);
    },
    setdisbursementType(e){
        // console.log(e.target.value)
        this.currentOrder.set_disbursement_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setInKindTransactionType(e){
        // console.log(e.target.value)
        this.currentOrder.set_in_kind_transaction_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    setCashTransactionType(e){
        // console.log(e.target.value)
        this.currentOrder.set_cash_transaction_type(e.target.value);
        this.pos.db.add_order(this.currentOrder.export_as_JSON());
    },
    open_fee_vouchers(){
        this.pos.showScreen("FeeVoucherManagementScreen");
    },
    async loadProductFromDB() {
        const product_ids=await super.loadProductFromDB();
        console.log("product_ids",product_ids)
        return product_ids
    }
})
ProductsWidget.template = "pos_enhancement.ProductsWidget";