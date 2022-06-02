from odoo import models, api, fields, tools, _
import logging
_logger = logging.getLogger(__name__)

class ContactLead(models.Model):
    _name = "contact.lead"
    _desc = 'Contact Lead'
    _auto = False


    #name = fields.Char(string='Partner Email')
    #company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    display_name = fields.Char(string="Display Name", compute="_compute_display_name")
    partner_id = fields.Many2one('res.partner', string='Partner')
    partner_name = fields.Many2one(string='Partner Name')
    partner_email = fields.Char(string='Partner Email')
    partner_phone = fields.Char(string='Partner Phone')
    partner_street = fields.Char(string='Partner Street')
    partner_street2 = fields.Char(string='Partner Street2')
    partner_city = fields.Char(string='Partner City')
    partner_state = fields.Many2one('res.country.state', string='Partner state')
    partner_zip = fields.Char(string='Partner Zip')
    partner_country = fields.Many2one('res.country', string='Partner Country')
    partner_address_type = fields.Selection(string='Address Type', related = 'partner_id.type', stored=True)
    lead_id = fields.Many2one('crm.lead', string='Lead')
    lead_name = fields.Char(string='Lead Name')
    contact_name = fields.Char(string='Contact Name')
    lead_phone = fields.Char(string='Lead Phone No.')
    lead_email = fields.Char(string='Lead Email')
    lead_city = fields.Char(string='Lead City')
    lead_state = fields.Char(string='Lead State')
    
    
    search_field = fields.Char(string="Search Field", compute="_compute_search_field", search="_search_computed_field")

    #company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.user.company_id)

    @api.depends('lead_id')
    def _compute_display_name(self):
        for record in self:
            record['display_name'] = "%s / %s" % (
                record.contact_name if record.contact_name else "Not Specified", 
                record.lead_id.display_name if record.lead_id and record.lead_id.display_name else "Not Specified"
            )
    
    @api.depends('lead_id', 'partner_id')
    def _compute_search_field(self):
        for record in self:
            lead_name_hack = record.lead_name.replace("_unknown('","").replace("',)"," ") if record.lead_name else ""
            partner_name_hack = str(record.partner_name).replace("_unknown('","").replace("',)"," ") if record.partner_name else ""
            record['search_field'] = ("%s %s %s %s %s %s %s %s %s %s %s" % (
                (lead_name_hack),
                (record.contact_name if record.contact_name else ""),
                (record.lead_phone if record.lead_phone else ""),
                (record.lead_email if record.lead_email else ""),
                (record.lead_city if record.lead_city else ""),
                (record.lead_state if record.lead_state else ""),
                (partner_name_hack),
                (record.partner_phone if record.partner_phone else ""),
                (record.partner_email if record.partner_email else ""),
                (record.partner_city if record.partner_city else ""),
                (record.partner_state.display_name if record.partner_state else "")
            ))
    
    def _search_computed_field(self, operator, value): 
        records = self.env['contact.lead'].search([]).filtered(lambda x : value in x.search_field)
        return [('id', "=", [x.id for x in records] if records else False )]
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            SELECT 
                row_number() OVER() AS id,
                contact_lead_data.lead_id,
                contact_lead_data.lead_name, 
                contact_lead_data.lead_phone,  
                contact_lead_data.lead_email,
                contact_lead_data.lead_city,
                contact_lead_data.lead_state,
                contact_lead_data.contact_name,  
                contact_lead_data.partner_id, 
                contact_lead_data.partner_name, 
                contact_lead_data.partner_phone, 
                contact_lead_data.partner_email,  
                contact_lead_data.partner_street,  
                contact_lead_data.partner_street2,  
                contact_lead_data.partner_city,  
                contact_lead_data.partner_state,  
                contact_lead_data.partner_zip,  
                contact_lead_data.partner_country
            FROM
            (SELECT
                null as lead_id,
                null as lead_name,
                null as lead_phone,
                null as lead_email,
                null as lead_city,
                null as lead_state,
                null as contact_name,
                id as partner_id,
                name as partner_name,
                email as partner_email,
                phone as partner_phone,
                street as partner_street,
                street2 as partner_street2,
                city as partner_city,
                state_id as partner_state,
                zip as partner_zip,
                country_id as partner_country
            FROM res_partner
            UNION
            SELECT
                lead.id as lead_id,
                lead.name as lead_name,
                lead.phone as lead_phone,
                lead.email_from as lead_email,
                lead.city as lead_city,
                lead.state_id as lead_state,
                lead.contact_name as contact_name,
                partner.id as partner_id,
                partner.name as partner_name,
                partner.email as partner_email,
                partner.phone as partner_phone,
                partner.street as partner_street,
                partner.street2 as partner_street2,
                partner.city as partner_city,
                partner.state_id as partner_state,
                partner.zip as partner_zip,
                partner.country_id as partner_country
            FROM crm_lead lead
            LEFT JOIN
            res_partner partner ON lead.partner_id = partner.id) as contact_lead_data
        )""" % (self._table))
