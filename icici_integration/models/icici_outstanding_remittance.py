from odoo import fields, models
from odoo.exceptions import UserError


class IciciOutstandingRemittance(models.Model):
    """One record per DTAssignment returned by IRM - Fetch Outstanding Remittance."""
    _name = 'icici.outstanding.remittance'
    _description = 'ICICI Outstanding Remittance'
    _inherit = ['icici.api.mixin']
    _order = 'credit_advice_value_date desc, id desc'
    _rec_name = 'grs_reference_no'

    _ICICI_MAP = {
        'GRSReferenceNo': 'grs_reference_no',
        'TransactionType': 'transaction_type',
        'IECode': 'ie_code',
        'TransactionStatus': 'transaction_status',
        'AuthoriserRemarks': 'authoriser_remarks',
        'SendersReference': 'senders_reference',
        'CreditAdviceValueDate': 'credit_advice_value_date',
        'Currency': 'currency_code',
        'Amount': 'amount',
        'USDEquivalent': 'usd_equivalent',
        'CreditAdviceNostro': 'credit_advice_nostro',
        'OrderingCustomer': 'ordering_customer',
        'OrderingCustomerDetails': 'ordering_customer_details',
        'OrderingInstitution': 'ordering_institution',
        'SendersCorrespondent': 'senders_correspondent',
        'BeneficiaryCustomer': 'beneficiary_customer',
        'BeneficiaryCustomerDetails': 'beneficiary_customer_details',
        'RemittanceInformation': 'remittance_information',
        'AccountWithInstitution': 'account_with_institution',
        'SenderToReceiverInformation': 'sender_to_receiver_information',
        'DealAmount': 'deal_amount',
        'ServicingInstitutionReference': 'servicing_institution_reference',
        'ReferenceNumber': 'reference_number',
        'ValueDate': 'value_date',
        'SupplementaryDetails': 'supplementary_details',
        'Nostro': 'nostro',
        'InformationToAccountOwner': 'information_to_account_owner',
        'AccountNumber': 'account_number',
        'AccountDescription': 'account_description',
        'BillID': 'bill_id',
        'OutstandingAmount': 'outstanding_amount',
        'OtherPartyDetails': 'other_party_details',
        'HUBBranch': 'hub_branch',
        'ChargesBorneBy': 'charges_borne_by',
        'Remarks': 'remarks',
        'OrderingInstitutionCountry': 'ordering_institution_country',
        'OrderingCustomerCountry': 'ordering_customer_country',
    }

    grs_reference_no = fields.Char('GRS Reference No', required=True, index=True, readonly=True)
    customer_id = fields.Char(readonly=True)
    credit_accounts = fields.Text(readonly=True)
    gst_details = fields.Text('GST Details', readonly=True)
    transaction_type = fields.Char(readonly=True)
    ie_code = fields.Char('IE Code', readonly=True)
    transaction_status = fields.Char(readonly=True)
    authoriser_remarks = fields.Text(readonly=True)
    senders_reference = fields.Char(readonly=True)
    credit_advice_value_date = fields.Datetime(readonly=True)
    currency_code = fields.Char('Currency', readonly=True)
    amount = fields.Float(readonly=True)
    usd_equivalent = fields.Float('USD Equivalent', readonly=True)
    credit_advice_nostro = fields.Char(readonly=True)
    ordering_customer = fields.Char(readonly=True)
    ordering_customer_details = fields.Text(readonly=True)
    ordering_institution = fields.Char(readonly=True)
    senders_correspondent = fields.Char(readonly=True)
    beneficiary_customer = fields.Char(readonly=True)
    beneficiary_customer_details = fields.Text(readonly=True)
    remittance_information = fields.Text(readonly=True)
    account_with_institution = fields.Char(readonly=True)
    sender_to_receiver_information = fields.Text(readonly=True)
    deal_amount = fields.Float(readonly=True)
    servicing_institution_reference = fields.Char(readonly=True)
    reference_number = fields.Char(readonly=True)
    value_date = fields.Datetime(readonly=True)
    supplementary_details = fields.Text(readonly=True)
    nostro = fields.Char(readonly=True)
    information_to_account_owner = fields.Text(readonly=True)
    account_number = fields.Char(readonly=True)
    account_description = fields.Char(readonly=True)
    bill_id = fields.Char('Bill ID', readonly=True)
    outstanding_amount = fields.Float(readonly=True)
    other_party_details = fields.Text(readonly=True)
    hub_branch = fields.Char('HUB Branch', readonly=True)
    charges_borne_by = fields.Char(readonly=True)
    remarks = fields.Text(readonly=True)
    ordering_institution_country = fields.Char(readonly=True)
    ordering_customer_country = fields.Char(readonly=True)

    _grs_company_uniq = models.Constraint('UNIQUE(grs_reference_no, company_id)',
                                          'This remittance already exists for the company.')

    def fetch_from_api(self, user_id, aggr_id, urn, account_no, customer_id):
        config = self.env['icici.config']._get_config()
        if not config.corp_id:
            raise UserError('Configure Corporate ID first.')
        result = config.call_api('outstanding_remittance', {
            'corp_id': config.corp_id, 'user_id': user_id, 'aggr_id': aggr_id,
            'urn': urn, 'account_no': account_no, 'customer_id': customer_id,
        })
        meta = result['meta']
        statuses = []
        for item in result['items']:
            statuses.append(self._icici_upsert(
                item, 'grs_reference_no', extra=meta, hash_source={'assignment': item, 'customer': meta},
                label='IRM Fetch Outstanding Remittance response')[1])
        return self._icici_summary(statuses)
