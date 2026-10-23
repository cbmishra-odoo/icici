"""Fetch wizards. Field names are the exact request parameter names of each API."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class IciciFetchIrmWizard(models.TransientModel):
    _name = 'icici.fetch.irm.wizard'
    _description = 'Fetch IRM List'

    fromRemittanceDate = fields.Date(required=True, default=lambda self: fields.Date.today().replace(day=1))
    toRemittanceDate = fields.Date(required=True, default=fields.Date.today)

    def action_fetch(self):
        self.ensure_one()
        if self.fromRemittanceDate > self.toRemittanceDate:
            raise UserError('fromRemittanceDate must not be after toRemittanceDate.')
        message = self.env['icici.irm'].fetch_from_api(self.fromRemittanceDate, self.toRemittanceDate)
        return self.env['icici.irm']._notify(message)


class IciciFetchSettledWizard(models.TransientModel):
    _name = 'icici.fetch.settled.wizard'
    _description = 'Fetch Settled IRM'

    remittanceRefNoList = fields.Text(
        required=True, help='Remittance reference numbers, one per line or comma separated. '
                            'Pre-filled with the IRMs whose settled details are not fetched yet.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'remittanceRefNoList' in fields_list:
            pending = self.env['icici.irm'].search([('settled_irm_ids', '=', False)])
            res['remittanceRefNoList'] = '\n'.join(pending.mapped('remittanceRefNo'))
        return res

    def action_fetch(self):
        self.ensure_one()
        refs = [r.strip() for r in self.remittanceRefNoList.replace(',', '\n').splitlines()]
        message = self.env['icici.settled.irm'].fetch_from_api(refs)
        return self.env['icici.settled.irm']._notify(message)


class IciciFetchShippingWizard(models.TransientModel):
    _name = 'icici.fetch.shipping.wizard'
    _description = 'Fetch Outstanding Shipping Bill List'

    type = fields.Char(required=True, default='GOODS')
    fromBillDate = fields.Date(required=True)
    toBillDate = fields.Date(required=True, default=fields.Date.today)

    def action_fetch(self):
        self.ensure_one()
        if self.fromBillDate > self.toBillDate:
            raise UserError('fromBillDate must not be after toBillDate.')
        message = self.env['icici.shipping.bill'].fetch_from_api(self.type, self.fromBillDate, self.toBillDate)
        return self.env['icici.shipping.bill']._notify(message)


class IciciFetchShippingDetailWizard(models.TransientModel):
    _name = 'icici.fetch.shipping.detail.wizard'
    _description = 'Fetch Outstanding Shipping Bill Details'

    shippingBillNumbers = fields.Text(help='One per line or comma separated.')
    formNos = fields.Text(help='One per line or comma separated. Either shippingBillNumbers or formNos is mandatory.')

    @staticmethod
    def _split(text):
        return [x.strip() for x in (text or '').replace(',', '\n').splitlines() if x.strip()]

    def action_fetch(self):
        self.ensure_one()
        message = self.env['icici.shipping.bill'].fetch_details(
            self._split(self.shippingBillNumbers), self._split(self.formNos))
        return self.env['icici.shipping.bill']._notify(message)


class IciciFetchRemittanceWizard(models.TransientModel):
    _name = 'icici.fetch.remittance.wizard'
    _description = 'Fetch Outstanding Remittance'

    corp_id = fields.Char(required=True)
    user_id = fields.Char(required=True)
    aggr_id = fields.Char(required=True)
    urn = fields.Char(required=True)
    account_no = fields.Char(required=True)
    customer_id = fields.Char(required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['icici.config'].sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if config:
            if 'corp_id' in fields_list and config.corpId:
                res['corp_id'] = config.corpId
            for name in ('user_id', 'aggr_id', 'urn', 'account_no', 'customer_id'):
                if name in fields_list and config[name]:
                    res[name] = config[name]
        return res

    def action_fetch(self):
        self.ensure_one()
        message = self.env['icici.outstanding.remittance'].fetch_from_api(
            self.corp_id, self.user_id, self.aggr_id, self.urn, self.account_no, self.customer_id)
        return self.env['icici.outstanding.remittance']._notify(message)
