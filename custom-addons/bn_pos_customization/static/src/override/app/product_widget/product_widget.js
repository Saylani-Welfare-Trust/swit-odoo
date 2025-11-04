/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        const { db } = this.pos;
        let list = [];
        var parent_check = db.get_category_by_id(this.selectedCategoryId)
        if (this.searchWord !== "") {
            list = db.search_product_in_category(this.selectedCategoryId, this.searchWord);
        } else {
            if(parent_check.parent_id) {
                list = db.get_product_by_category(this.selectedCategoryId);
            }
            else {
                list = []
            }
        }

        // Commented below line to not generate list when category is not selected
        // list = list.filter((product) => !this.getProductListToNotDisplay().includes(product.id));
        
        return list.sort(function (a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }
})