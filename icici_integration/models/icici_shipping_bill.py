from odoo import api, fields, models
from odoo.exceptions import UserError

from .icici_utils import parse_date, to_float


class IciciShippingBill(models.Model):
    """Outstanding shipping bill: list from the list API, form details from the details API.

    Field names are the exact names used by the API responses.
    """
    _name = 'icici.shipping.bill'
    _description = 'ICICI Outstanding Shipping Bill'
    _inherit = ['icici.api.mixin']
    _order = 'shippingDate desc, id desc'
    _rec_name = 'shippingBillNo'

    # Fetch Outstanding Shipping Bill List
    _ICICI_MAP = {k: k for k in (
        'shippingBillNo',
        'shippingDate',
        'portCode',
    )}
    # Fetch Outstanding Shipping Bill Details
    _ICICI_DETAIL_MAP = {k: k for k in (
        'adCode',
        'ieCode',
        'exportAgency',
        'portCode',
        'formNo',
        'shippingBillNo',
        'shippingBillDate',
        'leoDate',
        'dueDate',
        'message',
    )}

    shippingBillNo = fields.Char(required=True, index=True)
    shippingDate = fields.Date()
    portCode = fields.Char()
    adCode = fields.Char()
    ieCode = fields.Char()
    exportAgency = fields.Char()
    formNo = fields.Char()
    shippingBillDate = fields.Date()
    leoDate = fields.Date()
    dueDate = fields.Date()
    message = fields.Char()
    invoiceList = fields.One2many('icici.shipping.bill.invoice', 'bill_id', string='invoiceList')
    detail_hash = fields.Char(readonly=True, copy=False)
    detail_response = fields.Text('Details API Response', readonly=True, copy=False)
    detail_fetched = fields.Datetime(readonly=True, copy=False)

    _bill_company_uniq = models.Constraint('UNIQUE("shippingBillNo", company_id)',
                                           'This shipping bill already exists for the company.')

    def fetch_from_api(self, type, fromBillDate, toBillDate):
        config = self.env['icici.config']._get_config()
        if not (config.corpId and config.ieCode):
            raise UserError('Configure corpId and ieCode first.')
        result = config.call_api('shipping_list', {
            'corpId': config.corpId, 'ieCode': config.ieCode, 'type': type,
            'fromBillDate': fields.Date.to_date(fromBillDate).strftime('%d-%m-%Y'),
            'toBillDate': fields.Date.to_date(toBillDate).strftime('%d-%m-%Y'),
        })
        statuses = [self._icici_upsert(item, 'shippingBillNo',
                                       label='Fetch Outstanding Shipping Bill List response')[1]
                    for item in result['items']]
        return self._icici_summary(statuses)

    @api.model
    def fetch_details(self, shippingBillNumbers=None, formNos=None):
        """Fetch Outstanding Shipping Bill Details for the given numbers (either list may be empty, not both)."""
        shippingBillNumbers = [n for n in (shippingBillNumbers or []) if n]
        formNos = [n for n in (formNos or []) if n]
        if not (shippingBillNumbers or formNos):
            raise UserError('Either shippingBillNumbers or formNos is mandatory.')
        config = self.env['icici.config']._get_config()
        if not (config.corpId and config.ieCode):
            raise UserError('Configure corpId and ieCode first.')
        result = config.call_api('shipping_detail', {
            'corpId': config.corpId, 'ieCode': config.ieCode,
            'shippingBillNumbers': shippingBillNumbers, 'formNos': formNos,
        })
        Invoice = self.env['icici.shipping.bill.invoice']
        statuses = []
        for item in result['items']:
            key = str(item.get('shippingBillNo') or '')
            if not key:
                continue
            record = self.search([('shippingBillNo', '=', key), ('company_id', '=', self.env.company.id)], limit=1)
            if not record:
                record = self.with_context(mail_create_nosubscribe=True, mail_create_nolog=True).create(
                    {'shippingBillNo': key, 'company_id': self.env.company.id})
            status = record._icici_apply(
                item, mapping=self._ICICI_DETAIL_MAP, hash_field='detail_hash', raw_field='detail_response',
                label='Fetch Outstanding Shipping Bill Details response')
            if status == 'updated':
                record.invoiceList.unlink()
                for invoice in item.get('invoiceList') or []:
                    Invoice.create(dict(Invoice._icici_vals(invoice), bill_id=record.id))
            record.detail_fetched = fields.Datetime.now()
            statuses.append(status)
        return self._icici_summary(statuses)

    def action_fetch_details(self):
        """Form button: fetch details of this bill from the details API."""
        self.ensure_one()
        message = self.fetch_details([self.shippingBillNo], [])
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'ICICI', 'message': message, 'type': 'success', 'sticky': False,
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}


class IciciShippingBillInvoice(models.Model):
    """Entries of invoiceList in the shipping bill details response."""
    _name = 'icici.shipping.bill.invoice'
    _description = 'ICICI Shipping Bill Invoice'
    _rec_name = 'invoiceNo'

    _ICICI_MAP = {k: k for k in (
        'invoiceNo',
        'fobCurrencyCode',
        'exportBillValue',
        'exportType',
        'invoiceDate',
    )}

    bill_id = fields.Many2one('icici.shipping.bill', required=True, ondelete='cascade')
    invoiceNo = fields.Char()
    fobCurrencyCode = fields.Char()
    exportBillValue = fields.Float(digits=(16, 4))
    exportType = fields.Char()
    invoiceDate = fields.Date()

    def _icici_vals(self, item):
        vals = {}
        for key in self._ICICI_MAP:
            if key not in item:
                continue
            ftype = self._fields[key].type
            value = item[key]
            vals[key] = parse_date(value) if ftype == 'date' else to_float(value) if ftype == 'float' \
                else (str(value) if value is not None else False)
        return vals
