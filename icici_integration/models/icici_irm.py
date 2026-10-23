from odoo import api, fields, models
from odoo.exceptions import UserError

from .icici_utils import parse_date


class IciciIrm(models.Model):
    """Result of the Fetch IRM List API (list API only, so list and form show the same data)."""
    _name = 'icici.irm'
    _description = 'ICICI IRM'
    _inherit = ['icici.api.mixin']
    _order = 'remittance_date desc, id desc'
    _rec_name = 'remittance_ref_no'

    _ICICI_MAP = {
        'remittanceRefNo': 'remittance_ref_no',
        'remittanceDate': 'remittance_date',
    }

    remittance_ref_no = fields.Char('Remittance Reference No', required=True, index=True, readonly=True)
    remittance_date = fields.Date(readonly=True)
    settled_irm_ids = fields.One2many('icici.settled.irm', 'irm_id', string='Settled IRM')
    settled_count = fields.Integer(compute='_compute_settled_count')

    _ref_company_uniq = models.Constraint('UNIQUE(remittance_ref_no, company_id)',
                                          'This IRM already exists for the company.')

    @api.depends('settled_irm_ids')
    def _compute_settled_count(self):
        for rec in self:
            rec.settled_count = len(rec.settled_irm_ids)

    @api.model
    def fetch_from_api(self, from_date, to_date):
        config = self.env['icici.config']._get_config()
        if not (config.corp_id and config.ie_code):
            raise UserError('Configure Corporate ID and IE Code first.')
        result = config.call_api('irm_list', {
            'corpId': config.corp_id,
            'ieCode': config.ie_code,
            'fromRemittanceDate': fields.Date.to_date(from_date).strftime('%d-%m-%Y'),
            'toRemittanceDate': fields.Date.to_date(to_date).strftime('%d-%m-%Y'),
        })
        statuses = [self._icici_upsert(item, 'remittance_ref_no', label='Fetch IRM List response')[1]
                    for item in result['items']]
        return self._icici_summary(statuses)

    def action_fetch_settled(self):
        """Fetch the settled IRM details of the selected IRMs."""
        message = self.env['icici.settled.irm'].fetch_from_api(self.mapped('remittance_ref_no'))
        return self.env['icici.settled.irm']._notify(message)

    def action_view_settled(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Settled IRM', 'res_model': 'icici.settled.irm',
            'view_mode': 'list,form', 'domain': [('irm_id', '=', self.id)],
        }
