/** @odoo-module **/
/**
 * Defines AbstractAwaitablePopup extending from AbstractAwaitablePopup
 */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _lt } from '@web/core/l10n/translation';
import  { onMounted, useRef, useState } from "@odoo/owl";


import { useBus, useService } from "@web/core/utils/hooks";
class Chequepopup extends AbstractAwaitablePopup {
    setup() {
        super.setup();

        this.ormService = useService("orm");
        this.action = useService("action");
        this.searchInput = useRef("search-input")
    
        this.state = useState({
            chequeorder:[],
            currentPage: 1,
            totalRecords: 0,
            limit: 10,
            
        });
        this.CommentRef = useRef('comment');
        onMounted(() => {
            this.get_report_category_analysis();
            this.state.isFilterVisible = false;
        });
        this.get_report_category_analysis = async () => {
            const offset = (this.state.currentPage - 1) * this.state.limit;

            try {
                const result = await this.ormService.call('pos.order', 'get_cheque_order', [this.state.activeId, this.env.services.pos.config.id, offset, this.state.limit]);
                this.state.chequeorder = result.orders;
                this.state.totalRecords = result.total_count;
               
            } catch (error) {
                console.error("Error fetching report data:", error);
            }
            
        };
        
        
        // onMounted(this.onMounted);
    }
    nextPage = () => {
        if (this.state.currentPage * this.state.limit < this.state.totalRecords) {
            this.state.currentPage += 1;
            this.get_report_category_analysis();
        }
    };
    prevPage = () => {
        if (this.state.currentPage > 1) {
            this.state.currentPage -= 1;
            this.get_report_category_analysis();
        }
    };

    async searchTasks(){
        const text = this.searchInput.el.value
        try {
            const result = await this.ormService.call('pos.order', 'get_cheque_order_specific', [this.state.activeId, this.env.services.pos.config.id, text]);
            this.state.chequeorder = result.orders;
            this.state.totalRecords = result.total_count;
           
        } catch (error) {
            console.error("Error fetching report data:", error);
        }
        // this.state.taskList = await this.orm.searchRead(this.model, [['name','ilike',text]], ["name", "color", "completed"])
    }
    Bouncecheque(orderid){
        this.ormService.call('pos.order', 'bounce_cheque', [this.state.activeId, orderid])
        .then(() => {
            this.get_report_category_analysis(); // Refresh the data
        })
        .catch(error => {
            console.error("Error bouncing cheque:", error);
        });
    
    }
    ClearChque(orderid){
        const result = this.ormService.call('pos.order', 'clear_cheque', [this.state.activeId,orderid])
        .then(() => {
            this.get_report_category_analysis(); // Refresh the data
        })
        .catch(error => {
            console.error("Error bouncing cheque:", error);
        });
    }

    Redeposite(orderid){
        const result = this.ormService.call('pos.order', 'redeposite_cheque', [this.state.activeId,orderid])
        .then(() => {
            this.get_report_category_analysis(); // Refresh the data
        })
        .catch(error => {
            console.error("Error bouncing cheque:", error);
        });  
    }

    Cancelledcheque(orderid){
        const result = this.ormService.call('pos.order', 'cancelled_cheque', [this.state.activeId,orderid])
        .then(() => {
            this.get_report_category_analysis(); // Refresh the data
        })
        .catch(error => {
            console.error("Error bouncing cheque:", error);
        });

    }
    
    
}



Chequepopup.template = 'Chequepopup';
Chequepopup.defaultProps = {
    cancelText: _lt('Cancel'),
    title: '',
    body: '',
};
export default Chequepopup;
