/** @odoo-module **/

import { onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ChequePopup extends AbstractAwaitablePopup {
    static template = "bn_pos_cheque.ChequePopup";

    async get_pos_cheque() {
        // console.log(this.pos);

        const shop = this.pos.config.id;

        const offset = (this.state.currentPage - 1) * this.state.limit;
            
        const result = await this.orm.call('pos.order', 'get_cheque_pos_order', [this.state.activeId, shop, offset, this.state.limit]);

        // console.log(result);
        
        this.state.chequeorder = result.orders;
        this.state.totalRecords = result.total_count;
    }

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.searchInput = useRef("search-input")
        
        this.title = this.props.title || "POS Cheque";
        
        this.state = useState({
            chequeorder: [],
            currentPage: 1,
            totalRecords: 0,
            limit: 10,
            isFilterVisible: false
        });

        onMounted(() => {
            this.get_pos_cheque();
            this.state.isFilterVisible = false
        });
    }

    next = () => {
        if (this.state.currentPage * this.state.limit < this.state.totalRecords) {
            this.state.currentPage += 1;
            
            this.get_pos_cheque();
        }
    }

    previous = () => {
        if (this.state.currentPage > 1) {
            this.state.currentPage -= 1;
            
            this.get_pos_cheque();
        }
    }

    async searchChequeNumber(){
        const shop = this.pos.config.id;
        
        const text = this.searchInput.el.value

        const result = await this.orm.call('pos.order', 'get_cheque_pos_order_specific', [shop, text]);
        
        this.state.chequeorder = result.orders;
        this.state.totalRecords = result.total_count;
    }
    
    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }
}