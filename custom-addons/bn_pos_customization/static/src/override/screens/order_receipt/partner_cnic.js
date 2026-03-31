// /** @odoo-module */

// import { registry } from "@web/core/registry";
// import { PosGlobalState } from "@point_of_sale/app/store/pos_global_state";

// const PosPartnerCnic = (PosGlobalState) => class extends PosGlobalState {
//     async _processData(loadedData) {
//         await super._processData(...arguments);

//         if (loadedData['res.partner']) {
//             for (let partner of loadedData['res.partner']) {
//                 partner.cnic_no = partner.cnic_no || false;
//             }
//         }
//     }
// };

// registry.category("pos_models").add("pos_partner_cnic", PosPartnerCnic);