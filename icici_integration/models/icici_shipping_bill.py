
from odoo import fields, models
from odoo.exceptions import UserError

from .icici_utils import parse_date, to_float


class IciciShippingBill(models.Model):
    """Outstanding shipping bill: list from the list API, form details from the details API."""
    _name = 'icici.shipping.bill'
    _description = 'ICICI Outstanding Shipping Bill'
    _inherit = ['icici.api.mixin']
    _order = 'shipping_date desc, id desc'
    _rec_name = 'shipping_bill_no'

    # Fetch Outstanding Shipping Bill List
    _ICICI_MAP = {
        'shippingBillNo': 'shipping_bill_no',
        'shippingDate': 'shipping_date',
        'portCode': 'port_code',
    }
    # Fetch Outstanding Shipping Bill Details
    _ICICI_DETAIL_MAP = {
        'adCode': 'ad_code',
        'ieCode': 'ie_code',
        'exportAgency': 'export_agency',
        'portCode': 'port_code',
        'formNo': 'form_no',
        'shippingBillNo': 'shipping_bill_no',
        'shippingBillDate': 'shipping_bill_date',
        'leoDate': 'leo_date',
        'dueDate': 'due_date',
        'message': 'detail_message',
    }

    shipping_bill_no = fields.Char(required=True, index=True, readonly=True)
    shipping_date = fields.Date('Shipping Date (list)', readonly=True)
    port_code = fields.Char(readonly=True)
    # details
    detail_hash = fields.Char(readonly=True, copy=False)
    detail_response = fields.Text('Details API Response', readonly=True, copy=False)
    detail_fetched = fields.Datetime(readonly=True, copy=False)
    ad_code = fields.Char('AD Code', readonly=True)
    ie_code = fields.Char('IE Code', readonly=True)
    export_agency = fields.Char(readonly=True)
    form_no = fields.Char(readonly=True)
    shipping_bill_date = fields.Date(readonly=True)
    leo_date = fields.Date('LEO Date', readonly=True)
    due_date = fields.Date(readonly=True)
    detail_message = fields.Char('Message', readonly=True)
    invoice_ids = fields.One2many('icici.shipping.bill.invoice', 'bill_id', string='Invoices', readonly=True)

    _bill_company_uniq = models.Constraint('UNIQUE(shipping_bill_no, company_id)',
                                           'This shipping bill already exists for the company.')

    def fetch_from_api(self, bill_type, from_date, to_date):
        config = self.env['icici.config']._get_config()
        if not (config.corp_id and config.ie_code):
            raise UserError('Configure Corporate ID and IE Code first.')
        result = config.call_api('shipping_list', {
            'corpId': config.corp_id, 'ieCode': config.ie_code, 'type': bill_type,
            'fromBillDate': fields.Date.to_date(from_date).strftime('%d-%m-%Y'),
            'toBillDate': fields.Date.to_date(to_date).strftime('%d-%m-%Y'),
        })
        statuses = [self._icici_upsert(item, 'shipping_bill_no',
                                       label='Fetch Outstanding Shipping Bill List response')[1]
                    for item in result['items']]
        return self._icici_summary(statuses)

    def action_fetch_details(self):
        """Form button: fetch details of this bill from the details API."""
        self.ensure_one()
        config = self.env['icici.config']._get_config()
        result = config.call_api('shipping_detail', {
            'corpId': config.corp_id, 'ieCode': config.ie_code,
            'shippingBillNumbers': [self.shipping_bill_no], 'formNos': [],
        })
        items = [i for i in result['items'] if str(i.get('shippingBillNo')) == self.shipping_bill_no]
        if not items:
            raise UserError('ICICI returned no details for shipping bill %s.' % self.shipping_bill_no)
        item = items[0]
        status = self._icici_apply(
            item, mapping=self._ICICI_DETAIL_MAP, hash_field='detail_hash', raw_field='detail_response',
            label='Fetch Outstanding Shipping Bill Details response')
        if status == 'updated':
            self.invoice_ids.unlink()
            for inv in item.get('invoiceList') or []:
                self.env['icici.shipping.bill.invoice'].create(
                    dict(self.env['icici.shipping.bill.invoice']._icici_vals(inv), bill_id=self.id))
        self.detail_fetched = fields.Datetime.now()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'ICICI', 'message': 'Details %s.' % status, 'type': 'success', 'sticky': False,
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}


class IciciShippingBillInvoice(models.Model):
    _name = 'icici.shipping.bill.invoice'
    _description = 'ICICI Shipping Bill Invoice'

    _ICICI_MAP = {
        'invoiceNo': 'invoice_no',
        'fobCurrencyCode': 'fob_currency_code',
        'exportBillValue': 'export_bill_value',
        'exportType': 'export_type',
        'invoiceDate': 'invoice_date',
    }

    bill_id = fields.Many2one('icici.shipping.bill', required=True, ondelete='cascade')
    invoice_no = fields.Char(readonly=True)
    fob_currency_code = fields.Char('FOB Currency', readonly=True)
    export_bill_value = fields.Float(readonly=True, digits=(16, 4))
    export_type = fields.Char(readonly=True)
    invoice_date = fields.Date(readonly=True)

    def _icici_vals(self, item):
        vals = {}
        for api_key, fname in self._ICICI_MAP.items():
            if api_key not in item:
                continue
            value, ftype = item[api_key], self._fields[fname].type
            vals[fname] = parse_date(value) if ftype == 'date' else to_float(value) if ftype == 'float' \
                else (str(value) if value is not None else False)
        return vals
