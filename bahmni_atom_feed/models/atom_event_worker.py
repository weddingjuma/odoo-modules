# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AtomEventWorker(models.Model):
    _name = 'atom.event.worker'
    _auto = False

    @api.multi
    def process_event(self, vals):
        '''Method getting triggered from Bahmni side'''
        _logger.info("vals")
        _logger.info(vals)
        category = vals.get("category")
#         patient_ref = vals.get("ref")
        if(category == "create.customer"):
            self._create_or_update_customer(vals)
        if category == 'create.drug.category':
            self.env['drug.service.create']._create_or_update_drug_category(vals)
        if category == "create.drug":
            self.env['drug.service.create']._create_or_update_drug(vals)
        if(category == "create.sale.order"):
            self.env['order.save.service'].create_orders(vals)
        if (category == 'create.drug.category'):
            self.env['drug.service.create']._create_or_update_drug_category(vals)
        if (category == 'create.drug.uom'):
            self.env['product.uom.service']._create_or_update_uom(vals)
        if (category == 'create.drug.uom.category'):
            self.env['product.uom.service']._create_or_update_uom_category(vals)
        if(category == "create.radiology.test"):
            self.env['drug.service.create']._create_or_update_service(vals, 'Radiology')
        if(category == "create.lab.test"):
            self.env['lab.test.service']._create_or_update_service(vals, 'Test')
        if(category == "create.lab.panel"):
            self.env['lab.panel.service']._create_or_update_service(vals, 'Panel')

        self._create_or_update_marker(vals)
        return {'success': True}

    @api.model
    def _create_or_update_marker(self, vals):
        '''Method to Create or Update entries for markers table for the event taking place'''
        is_failed_event = vals.get('is_failed_event',False)
        if(is_failed_event):
            return

        last_read_entry_id = vals.get('last_read_entry_id')
        feed_uri_for_last_read_entry = vals.get('feed_uri_for_last_read_entry')
        feed_uri = vals.get('feed_uri')

        # Rohan/Mujir - do not update markers for failed events (failed events have empty 'feed_uri_for_last_read_entry')
        if not feed_uri_for_last_read_entry or not feed_uri or "$param" in feed_uri_for_last_read_entry or "$param" in feed_uri:
            return

        marker = self.env['atom.feed.marker'].search([('feed_uri', '=', feed_uri)],
                                                     limit=1)

        if marker:
            self._update_marker(feed_uri_for_last_read_entry, last_read_entry_id, marker)
        else:
            self._create_marker(feed_uri_for_last_read_entry, last_read_entry_id, feed_uri)

    @api.model
    def _create_or_update_customer(self, vals):
        patient_ref = vals.get("ref")
        customer_vals = self._get_customer_vals(vals)
        # removing null values, as while updating null values in write method will remove old values
        for rec in customer_vals:
            if not customer_vals[rec]:
                del customer_vals[rec]
        existing_customer = self.env['res.partner'].search([('ref', '=', patient_ref)])
        if existing_customer:
            existing_customer.write(customer_vals)
        else:
            self.env['res.partner'].create(customer_vals)

    @api.model
    def _get_address_details(self, address):
        res = {}
        if address.get('address1'):
            res.update({'street': address['address1']})
        if address.get('address2'):
            res.update({'street2': address['address2']})
        # TO FIX: once from bahmni side country name is passed properly, replace with that key
        country = self.env.user.company_id.country_id
        state = False
        district = False
        if address.get("stateProvince"):
            state = self.env['res.country.state'].search([('name', '=ilike', address['stateProvince'])])
            if not state:
                # for now, from bahmni side, no country is getting passed, so using company's country id
                state = self.env['res.country.state'].create({'name': address['stateProvince'],
                                                              'country_id': country.id})
            res.update({'state_id': state.id})
        # TO FIX: for now, district is getting passed with country key from bahmni side.
        if address.get('country'):
            district = self.env['state.district'].search([('name', '=ilike', address['country'])])
            if not district:
                district = self.env['state.district'].create({'name': address['country'],
                                                              'state_id': state.id if state else state,
                                                              'country_id': country.id})
        # for now, from bahmni side, Taluka is sent as address3
        if address.get('address3'):
            # =ilike operator will ignore the case of letters while comparing
            tehsil = self.env['district.tehsil'].search([('name', '=ilike', address['address3'])])
            if not tehsil:
                tehsil = self.env['district.tehsil'].create({'name': address['address3'],
                                                             'district_id': district.id if district else False,
                                                             'state_id': state.id if state else False})
            res.update({'tehsil_id': tehsil.id})

    def _get_customer_vals(self, vals):
        res = {}
        res.update({'ref': vals.get('ref'),
                    'name': vals.get('name'),
                    'local_name': vals.get('local_name'),
                    'uuid': vals.get('uuid')})
        address_data = vals.get('preferredAddress')
        # get validated address details
        address_details = self._get_address_details(address_data)
        # update address details
        res.update(address_details)
        # update other details : for now there is only scope of updating contact.
        if vals.get('primaryContact'):
            res.update({'phone': vals['primaryContact']})
        return res
