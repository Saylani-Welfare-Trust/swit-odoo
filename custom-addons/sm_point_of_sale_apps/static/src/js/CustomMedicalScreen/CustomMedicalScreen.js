/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { MedicalScreen } from "@medical_equipment/js/medical_screen";

patch(MedicalScreen.prototype, {
    getCategories() {
        var category_list = [
            ...this.pos.db.get_category_ancestors_ids(this.pos.selectedCategoryId),
            this.pos.selectedCategoryId,
            ...this.pos.db.get_category_childs_ids(this.pos.selectedCategoryId),
        ]
            .map((id) => this.pos.db.category_by_id[id])
            .filter((category) => {
                if (!category) return false;
                // Check if category has medical equipment products
                const products = this.pos.db.get_product_by_category(category.id);
                return products.some((product) => product.is_medical_equipment);
            })
            .map((category) => {
                const isRootCategory = category.id === this.pos.db.root_category_id;
                const showSeparator =
                    !isRootCategory &&
                    [
                        ...this.pos.db.get_category_ancestors_ids(this.pos.selectedCategoryId),
                        this.pos.selectedCategoryId,
                    ].includes(category.id);
                return {
                    id: category.id,
                    name: !isRootCategory ? category.name : "",
                    icon: isRootCategory ? "fa-home fa-2x" : "",
                    separator: "fa-caret-right",
                    showSeparator,
                    imageUrl:
                        category?.has_image &&
                        `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`,
                };
            });
        var category_filter_0 = category_list.filter((category) => category.level == 'level_0');
        var category_filter_1 = category_list.filter((category) => category.level == 'level_1');
        var category_filter_2 = category_list.filter((category) => category.level == 'level_2');
        var category_filter_3 = category_list.filter((category) => category.level == 'level_3');
        var category_filter_4 = category_list.filter((category) => category.level == 'level_4');
        var category_filter_5 = category_list.filter((category) => category.level == 'level_5');
        var category_all = [{
            'category_level_0': category_filter_0,
            'category_level_1': category_filter_1,
            'category_level_2': category_filter_2,
            'category_level_3': category_filter_3,
            'category_level_4': category_filter_4,
            'category_level_5': category_filter_5,
        }]
        console.log(category_all);
        return category_all;
    }
});
