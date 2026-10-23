from odoo import fields, models
from odoo.exceptions import UserError


class IciciOutstandingRemittance(models.Model):
    """One record per DTAssignment returned by IRM - Fetch Outstanding Remittance.

    Field names are the exact names used by the API response.
    """
    _name = 'icici.outstanding.remittance'
    _description = 'ICICI Outstanding Remittance'
    _inherit = ['icici.api.mixin']
    _order = 'CreditAdviceValueDate desc, id desc'
    _rec_name = 'GRSReferenceNo'

    _ICICI_MAP = {k: k for k in (
        'GRSReferenceNo',
        'TransactionType',
        'IECode',
        'TransactionStatus',
        'AuthoriserRemarks',
        'SendersReference',
        'CreditAdviceValueDate',
        'Currency',
        'Amount',
        'USDEquivalent',
        'CreditAdviceNostro',
        'OrderingCustomer',
        'OrderingCustomerDetails',
        'OrderingInstitution',
        'SendersCorrespondent',
        'BeneficiaryCustomer',
        'BeneficiaryCustomerDetails',
        'RemittanceInformation',
        'AccountWithInstitution',
        'SenderToReceiverInformation',
        'DealAmount',
        'ServicingInstitutionReference',
        'ReferenceNumber',
        'ValueDate',
        'SupplementaryDetails',
        'Nostro',
        'InformationToAccountOwner',
        'AccountNumber',
        'AccountDescription',
        'BillID',
        'OutstandingAmount',
        'OtherPartyDetails',
        'HUBBranch',
        'ChargesBorneBy',
        'Remarks',
        'OrderingInstitutionCountry',
        'OrderingCustomerCountry',
    )}

    # CustomerDetails of the response
    CustomerID = fields.Char()
    CreditAccounts = fields.One2many('icici.outstanding.remittance.credit.account', 'remittance_id',
                                     string='CreditAccounts')
    GSTDetails = fields.One2many('icici.outstanding.remittance.gst.detail', 'remittance_id',
                                 string='GSTDetails')
    # DTAssignment
    GRSReferenceNo = fields.Char(required=True, index=True)
    TransactionType = fields.Char()
    IECode = fields.Char()
    TransactionStatus = fields.Char()
    AuthoriserRemarks = fields.Text()
    SendersReference = fields.Char()
    CreditAdviceValueDate = fields.Datetime()
    Currency = fields.Char()
    Amount = fields.Float()
    USDEquivalent = fields.Float()
    CreditAdviceNostro = fields.Char()
    OrderingCustomer = fields.Char()
    OrderingCustomerDetails = fields.Text()
    OrderingInstitution = fields.Char()
    SendersCorrespondent = fields.Char()
    BeneficiaryCustomer = fields.Char()
    BeneficiaryCustomerDetails = fields.Text()
    RemittanceInformation = fields.Text()
    AccountWithInstitution = fields.Char()
    SenderToReceiverInformation = fields.Text()
    DealAmount = fields.Float()
    ServicingInstitutionReference = fields.Char()
    ReferenceNumber = fields.Char()
    ValueDate = fields.Datetime()
    SupplementaryDetails = fields.Text()
    Nostro = fields.Char()
    InformationToAccountOwner = fields.Text()
    AccountNumber = fields.Char()
    AccountDescription = fields.Char()
    BillID = fields.Char()
    OutstandingAmount = fields.Float()
    OtherPartyDetails = fields.Text()
    HUBBranch = fields.Char()
    ChargesBorneBy = fields.Char()
    Remarks = fields.Text()
    OrderingInstitutionCountry = fields.Char()
    OrderingCustomerCountry = fields.Char()

    _grs_company_uniq = models.Constraint('UNIQUE("GRSReferenceNo", company_id)',
                                          'This remittance already exists for the company.')

    def fetch_from_api(self, corp_id, user_id, aggr_id, urn, account_no, customer_id):
        config = self.env['icici.config']._get_config()
        result = config.call_api('outstanding_remittance', {
            'corp_id': corp_id, 'user_id': user_id, 'aggr_id': aggr_id,
            'urn': urn, 'account_no': account_no, 'customer_id': customer_id,
        })
        meta = result['meta']
        statuses = []
        for item in result['items']:
            record, status = self._icici_upsert(
                item, 'GRSReferenceNo', extra={'CustomerID': meta.get('CustomerID') or False},
                hash_source={'assignment': item, 'customer': meta},
                label='IRM Fetch Outstanding Remittance response')
            statuses.append(status)
            if status in ('created', 'updated'):
                record.CreditAccounts.unlink()
                record.GSTDetails.unlink()
                for line in meta.get('CreditAccounts') or []:
                    self.env['icici.outstanding.remittance.credit.account'].create({
                        'remittance_id': record.id, 'AccountNo': line.get('AccountNo'),
                        'Currency': line.get('Currency')})
                for line in meta.get('GSTDetails') or []:
                    self.env['icici.outstanding.remittance.gst.detail'].create({
                        'remittance_id': record.id, 'GSTNumber': line.get('GSTNumber'),
                        'GSTType': line.get('GSTType'), 'GSTCustAccountNo': line.get('GSTCustAccountNo')})
        return self._icici_summary(statuses)


class IciciOutstandingRemittanceCreditAccount(models.Model):
    """CustomerDetails.CreditAccounts.CreditAccount entries."""
    _name = 'icici.outstanding.remittance.credit.account'
    _description = 'ICICI Outstanding Remittance Credit Account'
    _rec_name = 'AccountNo'

    remittance_id = fields.Many2one('icici.outstanding.remittance', required=True, ondelete='cascade')
    AccountNo = fields.Char()
    Currency = fields.Char()


class IciciOutstandingRemittanceGstDetail(models.Model):
    """CustomerDetails.GSTDetails.GSTDetail entries."""
    _name = 'icici.outstanding.remittance.gst.detail'
    _description = 'ICICI Outstanding Remittance GST Detail'
    _rec_name = 'GSTNumber'

    remittance_id = fields.Many2one('icici.outstanding.remittance', required=True, ondelete='cascade')
    GSTNumber = fields.Char()
    GSTType = fields.Char()
    GSTCustAccountNo = fields.Char()
