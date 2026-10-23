import hashlib
import json

from markupsafe import Markup

from odoo import fields, models

from .icici_utils import parse_date, parse_datetime, to_float


class IciciApiMixin(models.AbstractModel):
    """Shared behaviour: chatter, de-duplicating upsert, API-key to field mapping."""
    _name = 'icici.api.mixin'
    _description = 'ICICI API Record Mixin'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # API key -> field name. Overridden per model; every response key must be listed.
    _ICICI_MAP = {}

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    api_hash = fields.Char(readonly=True, copy=False)
    raw_response = fields.Text('API Response', readonly=True, copy=False)
    last_fetched = fields.Datetime(readonly=True, copy=False)

    def _icici_vals(self, item, mapping=None):
        vals = {}
        for api_key, fname in (mapping or self._ICICI_MAP).items():
            if api_key not in item:
                continue
            value, ftype = item[api_key], self._fields[fname].type
            if ftype == 'date':
                value = parse_date(value)
            elif ftype == 'datetime':
                value = parse_datetime(value)
            elif ftype == 'float':
                value = to_float(value)
            elif value is None:
                value = False
            elif isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2, ensure_ascii=False)
            else:
                value = str(value)
            vals[fname] = value
        return vals

    def _icici_post(self, title, text, changes=None):
        body = Markup('<p><b>%s</b></p>') % title
        if changes:
            rows = Markup('').join(Markup('<li>%s: %s &rarr; %s</li>') % (label, old or '-', new or '-')
                                   for label, old, new in changes)
            body += Markup('<ul>%s</ul>') % rows
        body += Markup('<pre>%s</pre>') % text
        self.with_context(mail_notrack=True).message_post(
            body=body, message_type='comment', subtype_xmlid='mail.mt_note')

    def _icici_apply(self, item, mapping=None, hash_field='api_hash', raw_field='raw_response',
                     extra=None, hash_source=None, label='API response'):
        """Write an API item on this record only when it changed. Returns 'updated' or 'unchanged'."""
        self.ensure_one()
        digest = hashlib.sha256(json.dumps(hash_source if hash_source is not None else item,
                                           sort_keys=True, default=str).encode()).hexdigest()
        now = fields.Datetime.now()
        if self[hash_field] == digest:
            self.last_fetched = now
            return 'unchanged'
        vals = dict(self._icici_vals(item, mapping), **(extra or {}))
        changes = []
        if self[hash_field]:  # an update, not the first fill
            for fname, new in vals.items():
                old = self[fname]
                if hasattr(old, 'ids'):
                    continue
                if (old or False) != (new or False):
                    changes.append((self._fields[fname].string, old, new))
        pretty = json.dumps(item, indent=2, ensure_ascii=False, default=str)
        vals.update({hash_field: digest, raw_field: pretty, 'last_fetched': now})
        self.with_context(mail_notrack=True).write(vals)
        self._icici_post(label if not changes else label + ' (updated)', pretty, changes)
        return 'updated'

    def _icici_upsert(self, item, key_field, extra=None, hash_source=None, label='API response'):
        """Create the record for an item, or update it only if its data changed.

        Returns (record, status) with status in created / updated / unchanged / skipped.
        """
        vals = self._icici_vals(item)
        key = vals.get(key_field)
        if not key:
            return self.browse(), 'skipped'
        record = self.search([(key_field, '=', key), ('company_id', '=', self.env.company.id)], limit=1)
        if record:
            return record, record._icici_apply(item, extra=extra, hash_source=hash_source, label=label)
        record = self.with_context(mail_create_nosubscribe=True, mail_create_nolog=True, mail_notrack=True).create({
            key_field: key, 'company_id': self.env.company.id})
        record._icici_apply(item, extra=extra, hash_source=hash_source, label=label)
        return record, 'created'

    def _icici_summary(self, statuses):
        counts = {s: statuses.count(s) for s in ('created', 'updated', 'unchanged', 'skipped')}
        return 'Created: %(created)s, updated: %(updated)s, unchanged: %(unchanged)s' % counts

    def _notify(self, message):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': 'ICICI', 'message': message, 'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window', 'res_model': self._name,
                         'view_mode': 'list,form', 'views': [(False, 'list'), (False, 'form')],
                         'name': self._description},
            },
        }
