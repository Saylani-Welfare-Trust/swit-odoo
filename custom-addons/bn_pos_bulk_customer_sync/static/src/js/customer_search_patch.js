/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CustomerCache } from "./customer_indexeddb";

/**
 * IMPORTANT - this file is the one part of the module you will definitely
 * need to hand-adjust before deploying.
 *
 * Odoo's POS customer/partner search lives in the partner list screen
 * component (in 17.0 this is generally PartnerListScreen, under
 * addons/point_of_sale/static/src/app/screens/partner_list/). The exact
 * class name and method that runs the search can differ by 17.0.x point
 * release. Find the method that currently does something like:
 *
 *     this.state.query.trim() -> partners.filter(p => p.name.includes(...))
 *
 * in YOUR installed source, and replace its body with a call into
 * CustomerCache below, keyed off what the cashier is typing. Because your
 * cashiers search by phone, route digit-only queries through the phone
 * index; keep a name-based fallback only for the rare non-digit search
 * (it can stay slower since it won't be the common path).
 *
 * Sketch (adapt names to your actual component):
 *
 * import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list_screen";
 *
 * patch(PartnerListScreen.prototype, {
 *     async searchPartner(query) {
 *         const digitsOnly = /^[0-9+\s-]+$/.test(query);
 *         if (digitsOnly && query.length >= 4) {
 *             return await CustomerCache.findByPhonePrefix(query.replace(/\s|-/g, ""));
 *         }
 *         // fall back to whatever name-search behavior already exists,
 *         // or add a "name" index lookup similarly to findByPhonePrefix.
 *         return super.searchPartner(query);
 *     },
 * });
 */

export const patchNotes =
    "See comments in this file - wire CustomerCache.findByPhonePrefix() into " +
    "your installed PartnerListScreen's search method.";
