odoo.define('captivea_edi.action_button_batch_merging', function (require) {
"use strict";
var core = require('web.core');
var ListController = require('web.ListController');
var rpc = require('web.rpc');
var session = require('web.session');
var _t = core._t;
ListController.include({
    events: {
    'click button.oe_action_add_to_batch': 'action_add_to_batch_merge',
    'click button.oe_action_merge_pick_batch': 'action_pick_batch_merge'
    },
    action_add_to_batch_merge: function () {
            var self =this
            var user = session.uid;
//            this.do_action({
//                name: 'Select Batch',
//                res_model: 'batch.selector',
//                /*view_id: self.env.ref('captivea_edi.batch_selector_form_view').id,*/
//                context: {'active_ids': this.getSelectedIds()},
//                views: [[false, 'form']],
//                type: 'ir.actions.act_window',
//                view_mode: "form",
//                target: 'new',
//                'domain': [('state', 'not in', ('done', 'cancel'))]
//            });
            rpc.query({
                model: 'stock.picking',
                method: 'add_picking_to_batch',
                args: [this.getSelectedIds()],
                context: {'active_ids': this.getSelectedIds()},
                }).then(function(data){
                   self.do_action(data)
                });
            },
      action_pick_batch_merge: function () {
            var self =this
            var user = session.uid;
            rpc.query({
                model: 'stock.picking',
                method: 'combine_pickings_and_make_batch',
                args: [this.getSelectedIds()],
                context: {'active_ids': this.getSelectedIds()},
                }).then(function(data){
                    self.do_action(data)
                });
            },

//   renderButtons: function($node) {
//   this._super.apply(this, arguments);
//       if (this.$buttons) {
////         this.$buttons.find('.oe_action_add_to_batch').click(this.action_add_to_batch_merge.bind(this)) ;
//            if(this.getSelectedIds().length <= 0){
//                var groupByButton = $node.find('.oe_action_merge_pick_batch');
//                groupByButton.remove();
//            }
//            else{
//            var groupByButton = $node.find('.oe_action_merge_pick_batch');
//                groupByButton.add();
//            }
//       }
//   },

   });
});