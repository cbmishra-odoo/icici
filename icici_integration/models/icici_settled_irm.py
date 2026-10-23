from odoo import fields, models
from odoo.exceptions import UserError

CHUNK = 10  # remittance numbers per API call


class IciciSettledIrm(models.Model):
    """Result of the Fetch Settled IRM API (list API only).

    Field names are the exact names used by the API response.
    """
    _name = 'icici.settled.irm'
    _description = 'ICICI Settled IRM'
    _inherit = ['icici.api.mixin']
    _order = 'remittanceDate desc, id desc'
    _rec_name = 'remittanceRefNo'

    _ICICI_MAP = {k: k for k in (
        'adCodeId',
        'outstandingAmount',
        'remittanceRefNo',
        'remittanceDate',
        'remittanceAmount',
        'ieCode',
        'utilisedAmount',
        'remittanceCurrencyCode',
        'remitterName',
        'remitterAddress',
        'remitterCountryCode',
        'remitterBankName',
        'swiftOtherBankRefNumber',
        'purposeOfRemittance',
        'expectedUtilizationDate',
        'status',
        'remarks',
        'remittanceType',
    )}

    adCodeId = fields.Char()
    outstandingAmount = fields.Float()
    remittanceRefNo = fields.Char(required=True, index=True)
    remittanceDate = fields.Date()
    remittanceAmount = fields.Float()
    ieCode = fields.Char()
    utilisedAmount = fields.Float()
    remittanceCurrencyCode = fields.Char()
    remitterName = fields.Char()
    remitterAddress = fields.Text()
    remitterCountryCode = fields.Char()
    remitterBankName = fields.Char()
    swiftOtherBankRefNumber = fields.Char()
    purposeOfRemittance = fields.Char()
    expectedUtilizationDate = fields.Date()
    status = fields.Char()
    remarks = fields.Text()
    remittanceType = fields.Char()
    irm_id = fields.Many2one('icici.irm', string='IRM', ondelete='set null')

    _ref_company_uniq = models.Constraint('UNIQUE("remittanceRefNo", company_id)',
                                          'This settled IRM already exists for the company.')

    def fetch_from_api(self, remittanceRefNoList):
        config = self.env['icici.config']._get_config()
        refs = list(dict.fromkeys(r.strip() for r in remittanceRefNoList if r and r.strip()))
        if not refs:
            raise UserError('No remittance reference numbers to fetch. Fetch the IRM List first.')
        if not (config.corpId and config.ieCode):
            raise UserError('Configure corpId and ieCode first.')
        irm_by_ref = {i.remittanceRefNo: i for i in self.env['icici.irm'].search([
            ('remittanceRefNo', 'in', refs), ('company_id', '=', self.env.company.id)])}
        statuses = []
        for start in range(0, len(refs), CHUNK):
            result = config.call_api('settled_irm', {
                'corpId': config.corpId, 'ieCode': config.ieCode,
                'remittanceRefNoList': refs[start:start + CHUNK],
            })
            for item in result['items']:
                irm = irm_by_ref.get(item.get('remittanceRefNo'))
                record, status = self._icici_upsert(
                    item, 'remittanceRefNo', extra={'irm_id': irm.id if irm else False},
                    label='Fetch Settled IRM response')
                statuses.append(status)
        return self._icici_summary(statuses)
