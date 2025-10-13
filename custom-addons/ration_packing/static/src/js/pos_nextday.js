odoo.define('ration_packing.ConfirmNextDay', function(require){
  const PosComponent = require('point_of_sale.PosComponent');
  const Registries = require('point_of_sale.Registries');

  class ConfirmNextDayButton extends PosComponent {
    async onClick() {
      const orders = this.env.pos.get('orders').models;
      orders.forEach(o => {
        if (o.get_state() === 'paid') {
          o.x_confirmed_for_next_day = true;
          o.save_to_db();  // persist flag
        }
      });
      this.showPopup('ConfirmPopup', {
        title: 'Next‑Day Requirements Confirmed',
        body: 'All current orders have been marked for next‑day planning.',
      });
    }
  }
  ConfirmNextDayButton.template = 'ConfirmNextDayButton';
  Registries.Component.add(ConfirmNextDayButton);
});
