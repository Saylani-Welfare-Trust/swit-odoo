/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";


export class Many2manyFieldTags extends Component {
  static template = "pos_enhancement.Many2manyFieldTags";

  setup() {
    this.orm = useService("orm");
    this.pos = usePos();
    this.inputEle = useRef("tagInput");
    this.attachmentIdsToProcess = [];
    this.state = useState({
      available_analytic_accounts: [],
      inputValue: "",
      selected_tags: [],
      searched_tags: [],
      showOptions: false
    });
    onWillStart(async () => {
        const available_analytic_accounts = await this.orm.searchRead("account.analytic.account", [],['name']);
        this.state.available_analytic_accounts = available_analytic_accounts
        this.state.searched_tags = available_analytic_accounts

        // console.log("available_analytic_accounts",available_analytic_accounts)
    })

}
  addTag(ev,id) {
    ev.preventDefault();
    const tag = this.state.available_analytic_accounts.find((t) => t.id === id);

    this.currentOrder.add_analytic_account(tag)
    this.state.showOptions = false
    this.state.inputValue=""
  }
  get currentOrder() {
    return this.pos.get_order();
}

  /**
   * Remove a tag from the list
   * @param {string} tag - The tag to remove
   */
  removeTag(tag) {
    this.currentOrder.remove_analytic_account(tag)
    // this.state.selected_tags = this.state.selected_tags.filter((t) => t !== tag);
  }
  get option_container_width() {
    return this.inputEle.el.clientWidth
  }
  toggleOptionStatus(ev) {
    console.log(ev)
    if (ev.type === "focus") {
      this.state.showOptions = true;
      return;
    }
    else if (ev.type === "blur") {
        setTimeout(() => {
            this.state.showOptions = false;
        },200)
        return;
    }
  }
  search(ev) {

    this.state.searched_tags= this.state.available_analytic_accounts.filter((t) => t.name.toLowerCase().includes(ev.target.value.toLowerCase()))


  }
  
}

Many2manyFieldTags.props = {};

        