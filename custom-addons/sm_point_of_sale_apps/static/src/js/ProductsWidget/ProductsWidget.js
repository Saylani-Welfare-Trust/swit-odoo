/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    setup() {
        super.setup();
        this.breadcrumb_category = [];
    },
    getCategories() {
        var category_list = [
            ...this.pos.db.get_category_ancestors_ids(this.pos.selectedCategoryId),
            this.pos.selectedCategoryId,
            ...this.pos.db.get_category_childs_ids(this.pos.selectedCategoryId),
        ]
        .map((id) => this.pos.db.category_by_id[id])
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
                level: !isRootCategory ? category.level: "level_0",
                separator: "fa-caret-right",
                showSeparator,
                imageUrl:category?.has_image && `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`,
            };
        });
        var category_filter_0 = category_list.filter((category) => category.level == 'level_0');
        var category_filter_1 = category_list.filter((category) => category.level == 'level_1');
        var category_filter_2 = category_list.filter((category) => category.level == 'level_2');
        var category_filter_3 = category_list.filter((category) => category.level == 'level_3');
        var category_filter_4 = category_list.filter((category) => category.level == 'level_4');
        var category_filter_5 = category_list.filter((category) => category.level == 'level_5');
        if(category_filter_1.length != 0) {
            category_filter_1.push({
                id: 0,
                name: "",
                icon: "fa-home fa-2x",
                level: "level_1",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl: '',
            })
        }
        if(category_filter_2.length != 0) {
            category_filter_2.push({
                id: 0,
                name: "",
                icon: "fa-home fa-2x",
                level: "level_2",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl: '',
            })
        }
        if(category_filter_3.length != 0) {
            category_filter_3.push({
                id: 0,
                name: "",
                icon: "fa-home fa-2x",
                level: "level_3",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl: '',
            })
        }
        if(category_filter_4.length != 0) {
            category_filter_4.push({
                id: 0,
                name: "",
                icon: "fa-home fa-2x",
                level: "level_4",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl: '',
            })
        }
        if(category_filter_5.length != 0) {
            category_filter_5.push({
                id: 0,
                name: "",
                icon: "fa-home fa-2x",
                level: "level_5",
                separator: "fa-caret-right",
                showSeparator: false,
                imageUrl: '',
            })
        }
        var breadcrumb_category_list = this.pos.db.get_category_by_id(this.pos.selectedCategoryId);
        if (breadcrumb_category_list) {
            var category_data = breadcrumb_category_list;
            this.breadcrumb_category.push({
                id: category_data.id,
                name: category_data.name,
            });
            var donationIndex = this.breadcrumb_category.findIndex(item => item.id === category_data.id) + 1;
            if (donationIndex !== -1 && donationIndex < this.breadcrumb_category.length) {
                this.breadcrumb_category.splice(donationIndex);
            }
        }
        this.breadcrumb_category = [...new Set(this.breadcrumb_category)];
        var sortById = (array) => array.sort((a, b) => a.id - b.id);
        sortById(category_filter_0);
        sortById(category_filter_1);
        sortById(category_filter_2);
        sortById(category_filter_3);
        sortById(category_filter_4);
        sortById(category_filter_5);
        var category_all = [{
            'category_level_0': category_filter_0,
            'category_level_1': category_filter_1,
            'category_level_2': category_filter_2,
            'category_level_3': category_filter_3,
            'category_level_4': category_filter_4,
            'category_level_5': category_filter_5,
            'breadcrumb_category': this.breadcrumb_category,
        }]
        var category_child_list = []
        var child_ids = this.pos.db.get_category_by_id(this.pos.selectedCategoryId)
        if('level' in child_ids) {
            if(child_ids) {
                var child_list = child_ids.child_id;
                var child_length = child_list.length;
                if(child_length != 0) {
                    for(var j = 0; j < child_list.length; j++) {
                        var child_level = this.pos.db.get_category_by_id(child_list[j])
                        if(child_level) {
                            if(child_level.level == 'level_0') {
                                category_all[0].category_level_0 = category_filter_0
                                category_all[0].category_level_1 = []
                                category_all[0].category_level_2 = []
                                category_all[0].category_level_3 = []
                                category_all[0].category_level_4 = []
                                category_all[0].category_level_5 = []
                            }
                            else if(child_level.level == 'level_1') {
                                category_all[0].category_level_0 = []
                                category_all[0].category_level_1 = category_filter_1
                                category_all[0].category_level_2 = []
                                category_all[0].category_level_3 = []
                                category_all[0].category_level_4 = []
                                category_all[0].category_level_5 = []
                            }
                            else if(child_level.level == 'level_2') {
                                category_all[0].category_level_0 = []
                                category_all[0].category_level_1 = []
                                category_all[0].category_level_2 = category_filter_2
                                category_all[0].category_level_3 = []
                                category_all[0].category_level_4 = []
                                category_all[0].category_level_5 = []
                            }
                            else if(child_level.level == 'level_3') {
                                category_all[0].category_level_0 = []
                                category_all[0].category_level_1 = []
                                category_all[0].category_level_2 = []
                                category_all[0].category_level_3 = category_filter_3
                                category_all[0].category_level_4 = []
                                category_all[0].category_level_5 = []
                            }
                            else if(child_level.level == 'level_4') {
                                category_all[0].category_level_0 = []
                                category_all[0].category_level_1 = []
                                category_all[0].category_level_2 = []
                                category_all[0].category_level_3 = []
                                category_all[0].category_level_4 = category_filter_4
                                category_all[0].category_level_5 = []
                            }
                            else if(child_level.level == 'level_5') {
                                category_all[0].category_level_0 = []
                                category_all[0].category_level_1 = []
                                category_all[0].category_level_2 = []
                                category_all[0].category_level_3 = []
                                category_all[0].category_level_4 = []
                                category_all[0].category_level_5 = category_filter_5
                            }
                        }
                    }
                }
                else {
                    if(child_ids.level == 'level_0') {
                        category_all[0].category_level_0 = category_filter_0
                        category_all[0].category_level_1 = []
                        category_all[0].category_level_2 = []
                        category_all[0].category_level_3 = []
                        category_all[0].category_level_4 = []
                        category_all[0].category_level_5 = []
                    }
                    else if(child_ids.level == 'level_1') {
                        category_all[0].category_level_0 = []
                        category_all[0].category_level_1 = category_filter_1
                        category_all[0].category_level_2 = []
                        category_all[0].category_level_3 = []
                        category_all[0].category_level_4 = []
                        category_all[0].category_level_5 = []
                    }
                    else if(child_ids.level == 'level_2') {
                        category_all[0].category_level_0 = []
                        category_all[0].category_level_1 = []
                        category_all[0].category_level_2 = category_filter_2
                        category_all[0].category_level_3 = []
                        category_all[0].category_level_4 = []
                        category_all[0].category_level_5 = []
                    }
                    else if(child_ids.level == 'level_3') {
                        category_all[0].category_level_0 = []
                        category_all[0].category_level_1 = []
                        category_all[0].category_level_2 = []
                        category_all[0].category_level_3 = category_filter_3
                        category_all[0].category_level_4 = []
                        category_all[0].category_level_5 = []
                    }
                    else if(child_ids.level == 'level_4') {
                        category_all[0].category_level_0 = []
                        category_all[0].category_level_1 = []
                        category_all[0].category_level_2 = []
                        category_all[0].category_level_3 = []
                        category_all[0].category_level_4 = category_filter_4
                        category_all[0].category_level_5 = []
                    }
                    else if(child_ids.level == 'level_5') {
                        category_all[0].category_level_0 = []
                        category_all[0].category_level_1 = []
                        category_all[0].category_level_2 = []
                        category_all[0].category_level_3 = []
                        category_all[0].category_level_4 = []
                        category_all[0].category_level_5 = category_filter_5
                    }
                }
            }
            else {
                category_all = [{
                    'category_level_0': [],
                    'category_level_1': [],
                    'category_level_2': [],
                    'category_level_3': [],
                    'category_level_4': [],
                    'category_level_5': [],
                    'breadcrumb_category': [],
                }]
            }
        }
        console.log(category_all)
        return category_all;
    },
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
        // list = list.filter((product) => !this.getProductListToNotDisplay().includes(product.id));
        return list.sort(function (a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }
});
