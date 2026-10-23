import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from .icici_utils import extract

_logger = logging.getLogger(__name__)

API_CODES = [
    ('irm_list', 'Fetch IRM List'),
    ('settled_irm', 'Fetch Settled IRM'),
    ('shipping_list', 'Fetch Outstanding Shipping Bill List'),
    ('shipping_detail', 'Fetch Outstanding Shipping Bill Details'),
    ('outstanding_remittance', 'IRM - Fetch Outstanding Remittance'),
]

UAT_A = 'https://uat-onprem-dmz-hybrid.icici.bank.in'
UAT_B = 'https://uat-onprem-dmz-hybrid.icicibank.com'  # host used in the Shipping Bill document
PROD = 'https://igateway.icicibank.com'

DEFAULT_ENDPOINTS = {
    'irm_list': (UAT_A + '/apibanking/live/corpapi/v2/edocs/fetchIrm',
                 PROD + '/apibanking/live/corpapi/v2/edocs/fetchIrm'),
    'settled_irm': (UAT_A + '/trade/v1/edocs/fetchremittances',
                    PROD + '/trade/v1/edocs/fetchremittances'),
    # The document for the list API gives no URL: fill it in once ICICI confirms it.
    'shipping_list': ('', ''),
    'shipping_detail': (UAT_B + '/apibanking/live/corpapi/ixc/edocs/v2/shipping-bills',
                        PROD + '/apibanking/live/corpapi/ixc/edocs/v2/shipping-bills'),
    'outstanding_remittance': (UAT_A + '/trade/v1/irm/WebService/Fetchinwardremittance',
                               PROD + '/trade/v1/irm/WebService/Fetchinwardremittance'),
}


class IciciConfig(models.Model):
    _name = 'icici.config'
    _description = 'ICICI API Configuration'

    name = fields.Char(default='ICICI Integration', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    environment = fields.Selection([('uat', 'UAT'), ('prod', 'Production')], default='uat', required=True)
    apikey = fields.Char('API Key (apikey)', groups='icici_integration.group_icici_manager')
    session_key = fields.Char(
        'x-session-key', groups='icici_integration.group_icici_manager',
        help='Value sent in the x-session-key header. ICICI has not documented how it is generated; '
             'override _get_session_key() once the specification is known.')
    corp_id = fields.Char('Corporate ID (corpId)')
    ie_code = fields.Char('IE Code (ieCode)')
    # Parameters of the Fetch Outstanding Remittance API (defaults for its fetch wizard)
    user_id = fields.Char('User ID')
    aggr_id = fields.Char('Aggregator ID')
    urn = fields.Char('URN')
    account_no = fields.Char('Account Number')
    customer_id = fields.Char('Customer ID')
    timeout = fields.Integer(default=60)
    endpoint_ids = fields.One2many('icici.config.endpoint', 'config_id', string='API URLs',
                                   default=lambda self: self._default_endpoints())

    _company_uniq = models.Constraint('UNIQUE(company_id)', 'Only one ICICI configuration is allowed per company.')

    @api.model
    def _default_endpoints(self):
        return [(0, 0, {'api_code': code, 'uat_url': urls[0], 'prod_url': urls[1]})
                for code, urls in DEFAULT_ENDPOINTS.items()]

    @api.model
    def _get_config(self):
        """Configuration of the current company (sudo: credentials are manager-only)."""
        config = self.sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            raise UserError('Please create the ICICI configuration (ICICI Trade > Configuration) first.')
        return config

    def _get_url(self, api_code):
        self.ensure_one()
        line = self.endpoint_ids.filtered(lambda l: l.api_code == api_code)[:1]
        url = line.uat_url if self.environment == 'uat' else line.prod_url
        if not url:
            raise UserError('No %s URL configured for "%s".' % (self.environment.upper(), dict(API_CODES)[api_code]))
        return url.strip()

    # ---- Hooks: the only places that depend on ICICI's (undocumented) security scheme ----
    def _get_session_key(self, payload):
        """Value of the x-session-key header. Currently the configured static value."""
        self.ensure_one()
        return self.session_key or ''

    def _prepare_body(self, payload):
        """Request body. Currently plain JSON; add payload encryption here if ICICI requires it."""
        return payload

    def _parse_response(self, response):
        """Hook to decrypt the response if ICICI encrypts it. Currently plain JSON."""
        return response.json()

    def call_api(self, api_code, payload):
        """POST payload to the API and return the normalised result (see icici_utils.extract)."""
        self.ensure_one()
        if not self.apikey:
            raise UserError('API Key is not configured.')
        url = self._get_url(api_code)
        headers = {
            'Content-Type': 'application/json',
            'apikey': self.apikey,
            'x-session-key': self._get_session_key(payload),
        }
        try:
            response = requests.post(url, json=self._prepare_body(payload), headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise UserError('Could not reach ICICI (%s). Check the URL and that this server IP is whitelisted.\n%s'
                            % (url, exc)) from exc
        _logger.info('ICICI %s -> HTTP %s', api_code, response.status_code)
        try:
            data = self._parse_response(response)
        except ValueError as exc:
            raise UserError('ICICI returned a non-JSON response (HTTP %s):\n%s'
                            % (response.status_code, response.text[:500])) from exc
        result = extract(api_code, data)
        if result['errors']:
            raise UserError('ICICI error (HTTP %s):\n%s' % (response.status_code, '\n'.join(result['errors'])))
        return result


class IciciConfigEndpoint(models.Model):
    _name = 'icici.config.endpoint'
    _description = 'ICICI API URL'

    config_id = fields.Many2one('icici.config', required=True, ondelete='cascade')
    api_code = fields.Selection(API_CODES, required=True, string='API')
    uat_url = fields.Char('UAT URL')
    prod_url = fields.Char('Production URL')

    _api_uniq = models.Constraint('UNIQUE(config_id, api_code)', 'Each API can appear only once.')
