from odoo import fields, models
from odoo.exceptions import UserError

CHUNK = 10  # remittance numbers per API call


class IciciSettledIrm(models.Model):
    """Result of the Fetch Settled IRM API (list API only)."""
    _name = 'icici.settled.irm'
    _description = 'ICICI Settled IRM'
    _inherit = ['icici.api.mixin']
    _order = 'remittance_date desc, id desc'
    _rec_name = 'remittance_ref_no'

    _ICICI_MAP = {
        'adCodeId': 'ad_code_id',
        'outstandingAmount': 'outstanding_amount',
        'remittanceRefNo': 'remittance_ref_no',
        'remittanceDate': 'remittance_date',
        'remittanceAmount': 'remittance_amount',
        'ieCode': 'ie_code',
        'utilisedAmount': 'utilised_amount',
        'remittanceCurrencyCode': 'remittance_currency_code',
        'remitterName': 'remitter_name',
        'remitterAddress': 'remitter_address',
        'remitterCountryCode': 'remitter_country_code',
        'remitterBankName': 'remitter_bank_name',
        'swiftOtherBankRefNumber': 'swift_other_bank_ref_number',
        'purposeOfRemittance': 'purpose_of_remittance',
        'expectedUtilizationDate': 'expected_utilization_date',
        'status': 'status',
        'remarks': 'remarks',
        'remittanceType': 'remittance_type',
    }

    remittance_ref_no = fields.Char('Remittance Reference No', required=True, index=True)
    irm_id = fields.Many2one('icici.irm', string='IRM', ondelete='set null')
    ad_code_id = fields.Char('AD Code')
    outstanding_amount = fields.Float()
    remittance_date = fields.Date()
    remittance_amount = fields.Float()
    ie_code = fields.Char('IE Code')
    utilised_amount = fields.Float()
    remittance_currency_code = fields.Char('Currency')
    remitter_name = fields.Char()
    remitter_address = fields.Text()
    remitter_country_code = fields.Char()
    remitter_bank_name = fields.Char()
    swift_other_bank_ref_number = fields.Char('SWIFT / Other Bank Ref No')
    purpose_of_remittance = fields.Char()
    expected_utilization_date = fields.Date()
    status = fields.Char()
    remarks = fields.Text()
    remittance_type = fields.Char()

    _ref_company_uniq = models.Constraint('UNIQUE(remittance_ref_no, company_id)',
                                          'This settled IRM already exists for the company.')

    def fetch_from_api(self, ref_numbers):
        config = self.env['icici.config']._get_config()
        refs = list(dict.fromkeys(r.strip() for r in ref_numbers if r and r.strip()))
        if not refs:
            raise UserError('No remittance reference numbers to fetch. Fetch the IRM List first.')
        if not (config.corp_id and config.ie_code):
            raise UserError('Configure Corporate ID and IE Code first.')
        irm_by_ref = {i.remittance_ref_no: i for i in self.env['icici.irm'].search([
            ('remittance_ref_no', 'in', refs), ('company_id', '=', self.env.company.id)])}
        statuses = []
        for start in range(0, len(refs), CHUNK):
            result = config.call_api('settled_irm', {
                'corpId': config.corp_id, 'ieCode': config.ie_code,
                'remittanceRefNoList': refs[start:start + CHUNK],
            })
            for item in result['items']:
                irm = irm_by_ref.get(item.get('remittanceRefNo'))
                record, status = self._icici_upsert(
                    item, 'remittance_ref_no', extra={'irm_id': irm.id if irm else False},
                    label='Fetch Settled IRM response')
                statuses.append(status)
        return self._icici_summary(statuses)
