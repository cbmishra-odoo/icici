from odoo import api, fields, models
from odoo.exceptions import UserError


class IciciIrm(models.Model):
    """Result of the Fetch IRM List API (list API only, so list and form show the same data).

    Field names are the exact names used by the API response.
    """
    _name = 'icici.irm'
    _description = 'ICICI IRM'
    _inherit = ['icici.api.mixin']
    _order = 'remittanceDate desc, id desc'
    _rec_name = 'remittanceRefNo'

    _ICICI_MAP = {k: k for k in (
        'remittanceRefNo',
        'remittanceDate',
    )}

    remittanceRefNo = fields.Char(required=True, index=True)
    remittanceDate = fields.Date()
    settled_irm_ids = fields.One2many('icici.settled.irm', 'irm_id', string='Settled IRM')
    settled_count = fields.Integer(compute='_compute_settled_count')

    _ref_company_uniq = models.Constraint('UNIQUE("remittanceRefNo", company_id)',
                                          'This IRM already exists for the company.')

    @api.depends('settled_irm_ids')
    def _compute_settled_count(self):
        for rec in self:
            rec.settled_count = len(rec.settled_irm_ids)

    @api.model
    def fetch_from_api(self, fromRemittanceDate, toRemittanceDate):
        config = self.env['icici.config']._get_config()
        if not (config.corpId and config.ieCode):
            raise UserError('Configure corpId and ieCode first.')
        result = config.call_api('irm_list', {
            'corpId': config.corpId,
            'ieCode': config.ieCode,
            'fromRemittanceDate': fields.Date.to_date(fromRemittanceDate).strftime('%d-%m-%Y'),
            'toRemittanceDate': fields.Date.to_date(toRemittanceDate).strftime('%d-%m-%Y'),
        })
        statuses = [self._icici_upsert(item, 'remittanceRefNo', label='Fetch IRM List response')[1]
                    for item in result['items']]
        return self._icici_summary(statuses)

    def action_fetch_settled(self):
        """Fetch the settled IRM details of the selected IRMs."""
        message = self.env['icici.settled.irm'].fetch_from_api(self.mapped('remittanceRefNo'))
        return self.env['icici.settled.irm']._notify(message)

    def action_view_settled(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Settled IRM', 'res_model': 'icici.settled.irm',
            'view_mode': 'list,form', 'domain': [('irm_id', '=', self.id)],
        }
