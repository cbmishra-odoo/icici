from odoo import api, fields, models
from odoo.exceptions import UserError


class IciciFetchIrmWizard(models.TransientModel):
    _name = 'icici.fetch.irm.wizard'
    _description = 'Fetch IRM List'

    from_date = fields.Date(required=True, default=lambda self: fields.Date.today().replace(day=1))
    to_date = fields.Date(required=True, default=fields.Date.today)

    def action_fetch(self):
        self.ensure_one()
        if self.from_date > self.to_date:
            raise UserError('From date must not be after To date.')
        message = self.env['icici.irm'].fetch_from_api(self.from_date, self.to_date)
        return self.env['icici.irm']._notify(message)


class IciciFetchSettledWizard(models.TransientModel):
    _name = 'icici.fetch.settled.wizard'
    _description = 'Fetch Settled IRM'

    irm_ids = fields.Many2many('icici.irm', string='IRMs',
                               help='Leave empty to use every IRM from the IRM List.')
    only_missing = fields.Boolean('Only IRMs not yet fetched', default=True)
    extra_refs = fields.Text('Additional reference numbers', help='One per line or comma separated.')

    def action_fetch(self):
        self.ensure_one()
        irms = self.irm_ids
        if not irms:
            domain = [('settled_irm_ids', '=', False)] if self.only_missing else []
            irms = self.env['icici.irm'].search(domain)
        refs = irms.mapped('remittance_ref_no')
        refs += [r.strip() for r in (self.extra_refs or '').replace(',', '\n').splitlines()]
        message = self.env['icici.settled.irm'].fetch_from_api(refs)
        return self.env['icici.settled.irm']._notify(message)


class IciciFetchShippingWizard(models.TransientModel):
    _name = 'icici.fetch.shipping.wizard'
    _description = 'Fetch Outstanding Shipping Bill List'

    bill_type = fields.Char('Type', required=True, default='GOODS')
    from_bill_date = fields.Date(required=True)
    to_bill_date = fields.Date(required=True, default=fields.Date.today)

    def action_fetch(self):
        self.ensure_one()
        if self.from_bill_date > self.to_bill_date:
            raise UserError('From date must not be after To date.')
        message = self.env['icici.shipping.bill'].fetch_from_api(
            self.bill_type, self.from_bill_date, self.to_bill_date)
        return self.env['icici.shipping.bill']._notify(message)


class IciciFetchRemittanceWizard(models.TransientModel):
    _name = 'icici.fetch.remittance.wizard'
    _description = 'Fetch Outstanding Remittance'

    user_id = fields.Char('User ID', required=True)
    aggr_id = fields.Char('Aggregator ID', required=True)
    urn = fields.Char('URN', required=True)
    account_no = fields.Char('Account Number', required=True)
    customer_id = fields.Char('Customer ID', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['icici.config'].sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        for name in ('user_id', 'aggr_id', 'urn', 'account_no', 'customer_id'):
            if name in fields_list and config[name]:
                res[name] = config[name]
        return res

    def action_fetch(self):
        self.ensure_one()
        message = self.env['icici.outstanding.remittance'].fetch_from_api(
            self.user_id, self.aggr_id, self.urn, self.account_no, self.customer_id)
        return self.env['icici.outstanding.remittance']._notify(message)
