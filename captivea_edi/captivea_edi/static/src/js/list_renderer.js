odoo.define('captivea_edi.action_button_batch_renderer', function (require) {
"use strict";
var core = require('web.core');
var ListRenderer = require('web.ListRenderer');
var rpc = require('web.rpc');
var session = require('web.session');
var _t = core._t;
ListRenderer.include({
    _onSelectRecord: function (ev) {
        this._super.apply(this, arguments);
        if(this.state && this.state.context && this.state.context.picking_type_code && this.state.context.picking_type_code == 'outgoing' && this.state.model == 'stock.picking' && this.selection && this.selection.length > 0){
            $('button.oe_action_merge_pick_batch').css('display','inline-block');
            $('button.oe_action_add_to_batch').css('display','inline-block');
        }
        else{
            $('button.oe_action_merge_pick_batch').css('display','none');
            $('button.oe_action_add_to_batch').css('display','none');
        }
    },
   });
});