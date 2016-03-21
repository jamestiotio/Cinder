# Copyright 2013 eBay Inc.
# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from xml.dom import minidom

from lxml import etree
import mock
import webob

from cinder.api.contrib import qos_specs_manage
from cinder.api import xmlutil
from cinder import context
from cinder import db
from cinder import exception
from cinder import test
from cinder.tests.unit.api import fakes
from cinder.tests.unit import fake_constants as fake
from cinder.tests.unit import fake_notifier


def stub_qos_specs(id):
    res = dict(name='qos_specs_' + str(id))
    res.update(dict(consumer='back-end'))
    res.update(dict(id=str(id)))
    specs = {"key1": "value1",
             "key2": "value2",
             "key3": "value3",
             "key4": "value4",
             "key5": "value5"}
    res.update(dict(specs=specs))
    return res


def stub_qos_associates(id):
    return [{
            'association_type': 'volume_type',
            'name': 'FakeVolTypeName',
            'id': 'FakeVolTypeID'}]


def return_qos_specs_get_all(context, filters=None, marker=None, limit=None,
                             offset=None, sort_keys=None, sort_dirs=None):
    return [
        stub_qos_specs(1),
        stub_qos_specs(2),
        stub_qos_specs(3),
    ]


def return_qos_specs_get_qos_specs(context, id):
    if id == "777":
        raise exception.QoSSpecsNotFound(specs_id=id)
    return stub_qos_specs(int(id))


def return_qos_specs_delete(context, id, force):
    if id == "777":
        raise exception.QoSSpecsNotFound(specs_id=id)
    elif id == "666":
        raise exception.QoSSpecsInUse(specs_id=id)
    pass


def return_qos_specs_delete_keys(context, id, keys):
    if id == "777":
        raise exception.QoSSpecsNotFound(specs_id=id)

    if 'foo' in keys:
        raise exception.QoSSpecsKeyNotFound(specs_id=id,
                                            specs_key='foo')


def return_qos_specs_update(context, id, specs):
    if id == "777":
        raise exception.QoSSpecsNotFound(specs_id=id)
    elif id == "888":
        raise exception.InvalidQoSSpecs(reason=id)
    elif id == "999":
        raise exception.QoSSpecsUpdateFailed(specs_id=id,
                                             qos_specs=specs)
    pass


def return_qos_specs_create(context, name, specs):
    if name == "666":
        raise exception.QoSSpecsExists(specs_id=name)
    elif name == "555":
        raise exception.QoSSpecsCreateFailed(name=id, qos_specs=specs)
    elif name == "444":
        raise exception.InvalidQoSSpecs(reason=name)
    pass


def return_qos_specs_get_by_name(context, name):
    if name == "777":
        raise exception.QoSSpecsNotFound(specs_id=name)

    return stub_qos_specs(int(name.split("_")[2]))


def return_get_qos_associations(context, id):
    if id == "111":
        raise exception.QoSSpecsNotFound(specs_id=id)
    elif id == "222":
        raise exception.CinderException()

    return stub_qos_associates(id)


def return_associate_qos_specs(context, id, type_id):
    if id == "111":
        raise exception.QoSSpecsNotFound(specs_id=id)
    elif id == "222":
        raise exception.QoSSpecsAssociateFailed(specs_id=id,
                                                type_id=type_id)
    elif id == "333":
        raise exception.QoSSpecsDisassociateFailed(specs_id=id,
                                                   type_id=type_id)

    if type_id == "1234":
        raise exception.VolumeTypeNotFound(
            volume_type_id=type_id)

    pass


def return_disassociate_all(context, id):
    if id == "111":
        raise exception.QoSSpecsNotFound(specs_id=id)
    elif id == "222":
        raise exception.QoSSpecsDisassociateFailed(specs_id=id,
                                                   type_id=None)


class QoSSpecManageApiTest(test.TestCase):

    def _create_qos_specs(self, name, values=None):
        """Create a transfer object."""
        if values:
            specs = dict(name=name, qos_specs=values)
        else:
            specs = {'name': name,
                     'qos_specs': {
                         'consumer': 'back-end',
                         'key1': 'value1',
                         'key2': 'value2'}}
        return db.qos_specs_create(self.ctxt, specs)['id']

    def setUp(self):
        super(QoSSpecManageApiTest, self).setUp()
        self.flags(host='fake')
        self.controller = qos_specs_manage.QoSSpecsController()
        self.ctxt = context.RequestContext(user_id='user_id',
                                           project_id='project_id',
                                           is_admin=True)
        self.qos_id1 = self._create_qos_specs("Qos_test_1")
        self.qos_id2 = self._create_qos_specs("Qos_test_2")
        self.qos_id3 = self._create_qos_specs("Qos_test_3")
        self.qos_id4 = self._create_qos_specs("Qos_test_4")

    @mock.patch('cinder.volume.qos_specs.get_all_specs',
                side_effect=return_qos_specs_get_all)
    def test_index(self, mock_get_all_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')
        res = self.controller.index(req)

        self.assertEqual(3, len(res['qos_specs']))

        names = set()
        for item in res['qos_specs']:
            self.assertEqual('value1', item['specs']['key1'])
            names.add(item['name'])
        expected_names = ['qos_specs_1', 'qos_specs_2', 'qos_specs_3']
        self.assertEqual(set(expected_names), names)

    @mock.patch('cinder.volume.qos_specs.get_all_specs',
                side_effect=return_qos_specs_get_all)
    def test_index_xml_response(self, mock_get_all_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')
        res = self.controller.index(req)
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/xml'
        req.headers['Accept'] = 'application/xml'
        res = req.get_response(fakes.wsgi_app())

        self.assertEqual(200, res.status_int)
        dom = minidom.parseString(res.body)
        qos_specs_response = dom.getElementsByTagName('qos_spec')

        names = set()
        for qos_spec in qos_specs_response:
            name = qos_spec.getAttribute('name')
            names.add(name)

        expected_names = ['qos_specs_1', 'qos_specs_2', 'qos_specs_3']
        self.assertEqual(set(expected_names), names)

    def test_index_with_limit(self):
        url = '/v2/%s/qos-specs?limit=2' % fake.project_id
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)

        self.assertEqual(2, len(res['qos_specs']))
        self.assertEqual(self.qos_id4, res['qos_specs'][0]['id'])
        self.assertEqual(self.qos_id3, res['qos_specs'][1]['id'])

        expect_next_link = ('http://localhost/v2/%s/qos-specs?limit'
                            '=2&marker=%s') % (
                                fake.project_id, res['qos_specs'][1]['id'])
        self.assertEqual(expect_next_link, res['qos_specs_links'][0]['href'])

    def test_index_with_offset(self):
        url = '/v2/fake/qos-specs?offset=1'
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)

        self.assertEqual(3, len(res['qos_specs']))

    def test_index_with_offset_out_of_range(self):
        url = '/v2/fake/qos-specs?offset=356576877698707'
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.index,
                          req)

    def test_index_with_limit_and_offset(self):
        url = '/v2/fake/qos-specs?limit=2&offset=1'
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)

        self.assertEqual(2, len(res['qos_specs']))
        self.assertEqual(self.qos_id3, res['qos_specs'][0]['id'])
        self.assertEqual(self.qos_id2, res['qos_specs'][1]['id'])

    def test_index_with_marker(self):
        url = '/v2/fake/qos-specs?marker=%s' % self.qos_id4
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)

        self.assertEqual(3, len(res['qos_specs']))

    def test_index_with_filter(self):
        url = '/v2/fake/qos-specs?id=%s' % self.qos_id4
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)

        self.assertEqual(1, len(res['qos_specs']))
        self.assertEqual(self.qos_id4, res['qos_specs'][0]['id'])

    def test_index_with_sort_keys(self):
        url = '/v2/fake/qos-specs?sort=id'
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)
        self.assertEqual(4, len(res['qos_specs']))
        expect_result = [self.qos_id1, self.qos_id2,
                         self.qos_id3, self.qos_id4]
        expect_result.sort(reverse=True)

        self.assertEqual(expect_result[0], res['qos_specs'][0]['id'])
        self.assertEqual(expect_result[1], res['qos_specs'][1]['id'])
        self.assertEqual(expect_result[2], res['qos_specs'][2]['id'])
        self.assertEqual(expect_result[3], res['qos_specs'][3]['id'])

    def test_index_with_sort_keys_and_sort_dirs(self):
        url = '/v2/fake/qos-specs?sort=id:asc'
        req = fakes.HTTPRequest.blank(url, use_admin_context=True)
        res = self.controller.index(req)
        self.assertEqual(4, len(res['qos_specs']))
        expect_result = [self.qos_id1, self.qos_id2,
                         self.qos_id3, self.qos_id4]
        expect_result.sort()

        self.assertEqual(expect_result[0], res['qos_specs'][0]['id'])
        self.assertEqual(expect_result[1], res['qos_specs'][1]['id'])
        self.assertEqual(expect_result[2], res['qos_specs'][2]['id'])
        self.assertEqual(expect_result[3], res['qos_specs'][3]['id'])

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.delete',
                side_effect=return_qos_specs_delete)
    def test_qos_specs_delete(self, mock_qos_delete, mock_qos_get_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/1')
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.controller.delete(req, 1)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.delete',
                side_effect=return_qos_specs_delete)
    def test_qos_specs_delete_not_found(self, mock_qos_delete,
                                        mock_qos_get_specs):
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/777')
            self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                              req, '777')
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.delete',
                side_effect=return_qos_specs_delete)
    def test_qos_specs_delete_inuse(self, mock_qos_delete,
                                    mock_qos_get_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/666')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPBadRequest, self.controller.delete,
                              req, '666')
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.delete',
                side_effect=return_qos_specs_delete)
    def test_qos_specs_delete_inuse_force(self, mock_qos_delete,
                                          mock_qos_get_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/666?force=True')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPInternalServerError,
                              self.controller.delete,
                              req, '666')
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.delete_keys',
                side_effect=return_qos_specs_delete_keys)
    def test_qos_specs_delete_keys(self, mock_qos_delete_keys):
        body = {"keys": ['bar', 'zoo']}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/666/delete_keys')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.controller.delete_keys(req, '666', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.delete_keys',
                side_effect=return_qos_specs_delete_keys)
    def test_qos_specs_delete_keys_qos_notfound(self, mock_qos_specs_delete):
        body = {"keys": ['bar', 'zoo']}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/777/delete_keys')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPNotFound,
                              self.controller.delete_keys,
                              req, '777', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.delete_keys',
                side_effect=return_qos_specs_delete_keys)
    def test_qos_specs_delete_keys_badkey(self, mock_qos_specs_delete):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/666/delete_keys')
        body = {"keys": ['foo', 'zoo']}

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPBadRequest,
                              self.controller.delete_keys,
                              req, '666', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.delete_keys',
                side_effect=return_qos_specs_delete_keys)
    def test_qos_specs_delete_keys_get_notifier(self, mock_qos_delete_keys):
        body = {"keys": ['bar', 'zoo']}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/666/delete_keys')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier,
                        autospec=True) as mock_get_notifier:
            self.controller.delete_keys(req, '666', body)
            mock_get_notifier.assert_called_once_with('QoSSpecs')

    @mock.patch('cinder.volume.qos_specs.create',
                side_effect=return_qos_specs_create)
    @mock.patch('cinder.volume.qos_specs.get_qos_specs_by_name',
                side_effect=return_qos_specs_get_by_name)
    @mock.patch('cinder.api.openstack.wsgi.Controller.validate_string_length')
    def test_create(self, mock_validate, mock_qos_get_specs,
                    mock_qos_spec_create):

        body = {"qos_specs": {"name": "qos_specs_1",
                              "key1": "value1"}}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            res_dict = self.controller.create(req, body)

            self.assertEqual(1, notifier.get_notification_count())
            self.assertEqual('qos_specs_1', res_dict['qos_specs']['name'])
            self.assertTrue(mock_validate.called)

    @mock.patch('cinder.volume.qos_specs.create',
                side_effect=return_qos_specs_create)
    def test_create_invalid_input(self, mock_qos_get_specs):
        body = {"qos_specs": {"name": "444",
                              "consumer": "invalid_consumer"}}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPBadRequest,
                              self.controller.create, req, body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.create',
                side_effect=return_qos_specs_create)
    @mock.patch('cinder.volume.qos_specs.get_qos_specs_by_name',
                side_effect=return_qos_specs_get_by_name)
    def test_create_conflict(self, mock_qos_get_specs, mock_qos_spec_create):
        body = {"qos_specs": {"name": "666",
                              "key1": "value1"}}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPConflict,
                              self.controller.create, req, body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.create',
                side_effect=return_qos_specs_create)
    @mock.patch('cinder.volume.qos_specs.get_qos_specs_by_name',
                side_effect=return_qos_specs_get_by_name)
    def test_create_failed(self, mock_qos_get_specs, mock_qos_spec_create):
        body = {"qos_specs": {"name": "555",
                              "key1": "value1"}}
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')

        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            self.assertRaises(webob.exc.HTTPInternalServerError,
                              self.controller.create, req, body)
            self.assertEqual(1, notifier.get_notification_count())

    def _create_qos_specs_bad_body(self, body):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs')
        req.method = 'POST'
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, body)

    def test_create_no_body(self):
        self._create_qos_specs_bad_body(body=None)

    def test_create_invalid_body(self):
        body = {'foo': {'a': 'b'}}
        self._create_qos_specs_bad_body(body=body)

    def test_create_missing_specs_name(self):
        body = {'qos_specs': {'a': 'b'}}
        self._create_qos_specs_bad_body(body=body)

    def test_create_malformed_entity(self):
        body = {'qos_specs': 'string'}
        self._create_qos_specs_bad_body(body=body)

    @mock.patch('cinder.volume.qos_specs.update',
                side_effect=return_qos_specs_update)
    def test_update(self, mock_qos_update):
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/555')
            body = {'qos_specs': {'key1': 'value1',
                                  'key2': 'value2'}}
            res = self.controller.update(req, '555', body)
            self.assertDictMatch(body, res)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.update',
                side_effect=return_qos_specs_update)
    def test_update_not_found(self, mock_qos_update):
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/777')
            body = {'qos_specs': {'key1': 'value1',
                                  'key2': 'value2'}}
            self.assertRaises(webob.exc.HTTPNotFound, self.controller.update,
                              req, '777', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.update',
                side_effect=return_qos_specs_update)
    def test_update_invalid_input(self, mock_qos_update):
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/888')
            body = {'qos_specs': {'key1': 'value1',
                                  'key2': 'value2'}}
            self.assertRaises(webob.exc.HTTPBadRequest,
                              self.controller.update,
                              req, '888', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.update',
                side_effect=return_qos_specs_update)
    def test_update_failed(self, mock_qos_update):
        notifier = fake_notifier.get_fake_notifier()
        with mock.patch('cinder.rpc.get_notifier', return_value=notifier):
            req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/999')
            body = {'qos_specs': {'key1': 'value1',
                                  'key2': 'value2'}}
            self.assertRaises(webob.exc.HTTPInternalServerError,
                              self.controller.update,
                              req, '999', body)
            self.assertEqual(1, notifier.get_notification_count())

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    def test_show(self, mock_get_qos_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/1')
        res_dict = self.controller.show(req, '1')

        self.assertEqual('1', res_dict['qos_specs']['id'])
        self.assertEqual('qos_specs_1', res_dict['qos_specs']['name'])

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    def test_show_xml_response(self, mock_get_qos_specs):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/1')
        res = self.controller.show(req, '1')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/xml'
        req.headers['Accept'] = 'application/xml'
        res = req.get_response(fakes.wsgi_app())

        self.assertEqual(200, res.status_int)
        dom = minidom.parseString(res.body)
        qos_spec_response = dom.getElementsByTagName('qos_spec')
        qos_spec = qos_spec_response.item(0)

        id = qos_spec.getAttribute('id')
        name = qos_spec.getAttribute('name')
        consumer = qos_spec.getAttribute('consumer')

        self.assertEqual(u'1', id)
        self.assertEqual('qos_specs_1', name)
        self.assertEqual('back-end', consumer)

    @mock.patch('cinder.volume.qos_specs.get_associations',
                side_effect=return_get_qos_associations)
    def test_get_associations(self, mock_get_assciations):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/associations')
        res = self.controller.associations(req, '1')

        self.assertEqual('FakeVolTypeName',
                         res['qos_associations'][0]['name'])
        self.assertEqual('FakeVolTypeID',
                         res['qos_associations'][0]['id'])

    @mock.patch('cinder.volume.qos_specs.get_associations',
                side_effect=return_get_qos_associations)
    def test_get_associations_xml_response(self, mock_get_assciations):
        req = fakes.HTTPRequest.blank('/v2/fake/qos-specs/1/associations')
        res = self.controller.associations(req, '1')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/xml'
        req.headers['Accept'] = 'application/xml'
        res = req.get_response(fakes.wsgi_app())

        self.assertEqual(200, res.status_int)
        dom = minidom.parseString(res.body)
        associations_response = dom.getElementsByTagName('associations')
        association = associations_response.item(0)

        id = association.getAttribute('id')
        name = association.getAttribute('name')
        association_type = association.getAttribute('association_type')

        self.assertEqual('FakeVolTypeID', id)
        self.assertEqual('FakeVolTypeName', name)
        self.assertEqual('volume_type', association_type)

    @mock.patch('cinder.volume.qos_specs.get_associations',
                side_effect=return_get_qos_associations)
    def test_get_associations_not_found(self, mock_get_assciations):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/111/associations')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.associations,
                          req, '111')

    @mock.patch('cinder.volume.qos_specs.get_associations',
                side_effect=return_get_qos_associations)
    def test_get_associations_failed(self, mock_get_associations):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/222/associations')
        self.assertRaises(webob.exc.HTTPInternalServerError,
                          self.controller.associations,
                          req, '222')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.associate_qos_with_type',
                side_effect=return_associate_qos_specs)
    def test_associate(self, mock_associate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/associate?vol_type_id=111')
        res = self.controller.associate(req, '1')

        self.assertEqual(202, res.status_int)

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.associate_qos_with_type',
                side_effect=return_associate_qos_specs)
    def test_associate_no_type(self, mock_associate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/associate')

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.associate, req, '1')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.associate_qos_with_type',
                side_effect=return_associate_qos_specs)
    def test_associate_not_found(self, mock_associate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/111/associate?vol_type_id=12')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.associate, req, '111')

        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/associate?vol_type_id=1234')

        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.associate, req, '1')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.associate_qos_with_type',
                side_effect=return_associate_qos_specs)
    def test_associate_fail(self, mock_associate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/222/associate?vol_type_id=1000')
        self.assertRaises(webob.exc.HTTPInternalServerError,
                          self.controller.associate, req, '222')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_qos_specs',
                side_effect=return_associate_qos_specs)
    def test_disassociate(self, mock_disassociate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/disassociate?vol_type_id=111')
        res = self.controller.disassociate(req, '1')
        self.assertEqual(202, res.status_int)

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_qos_specs',
                side_effect=return_associate_qos_specs)
    def test_disassociate_no_type(self, mock_disassociate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/disassociate')

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.disassociate, req, '1')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_qos_specs',
                side_effect=return_associate_qos_specs)
    def test_disassociate_not_found(self, mock_disassociate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/111/disassociate?vol_type_id=12')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.disassociate, req, '111')

        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/disassociate?vol_type_id=1234')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.disassociate, req, '1')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_qos_specs',
                side_effect=return_associate_qos_specs)
    def test_disassociate_failed(self, mock_disassociate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/333/disassociate?vol_type_id=1000')
        self.assertRaises(webob.exc.HTTPInternalServerError,
                          self.controller.disassociate, req, '333')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_all',
                side_effect=return_disassociate_all)
    def test_disassociate_all(self, mock_disassociate, mock_get_qos):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/1/disassociate_all')
        res = self.controller.disassociate_all(req, '1')
        self.assertEqual(202, res.status_int)

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_all',
                side_effect=return_disassociate_all)
    def test_disassociate_all_not_found(self, mock_disassociate, mock_get):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/111/disassociate_all')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.disassociate_all, req, '111')

    @mock.patch('cinder.volume.qos_specs.get_qos_specs',
                side_effect=return_qos_specs_get_qos_specs)
    @mock.patch('cinder.volume.qos_specs.disassociate_all',
                side_effect=return_disassociate_all)
    def test_disassociate_all_failed(self, mock_disassociate, mock_get):
        req = fakes.HTTPRequest.blank(
            '/v2/fake/qos-specs/222/disassociate_all')
        self.assertRaises(webob.exc.HTTPInternalServerError,
                          self.controller.disassociate_all, req, '222')


class TestQoSSpecsTemplate(test.TestCase):
    def setUp(self):
        super(TestQoSSpecsTemplate, self).setUp()
        self.serializer = qos_specs_manage.QoSSpecsTemplate()

    def test_qos_specs_serializer(self):
        fixture = {
            "qos_specs": [
                {
                    "specs": {
                        "key1": "v1",
                        "key2": "v2",
                    },
                    "consumer": "back-end",
                    "name": "qos-2",
                    "id": "61e7b72f-ef15-46d9-b00e-b80f699999d0"
                },
                {
                    "specs": {"total_iops_sec": "200"},
                    "consumer": "front-end",
                    "name": "qos-1",
                    "id": "e44bba5e-b629-4b96-9aa3-0404753a619b"
                }
            ]
        }

        output = self.serializer.serialize(fixture)
        root = etree.XML(output)
        xmlutil.validate_schema(root, 'qos_specs')
        qos_elems = root.findall("qos_spec")
        self.assertEqual(2, len(qos_elems))
        for i, qos_elem in enumerate(qos_elems):
            qos_dict = fixture['qos_specs'][i]

            # check qos_spec attributes
            for key in ['name', 'id', 'consumer']:
                self.assertEqual(str(qos_dict[key]), qos_elem.get(key))

            # check specs
            specs = qos_elem.find("specs")
            new_dict = {}
            for element in specs.iter(tag=etree.Element):
                # skip root element for specs
                if element.tag == "specs":
                    continue
                new_dict.update({element.tag: element.text})

            self.assertDictMatch(qos_dict['specs'], new_dict)


class TestAssociationsTemplate(test.TestCase):
    def setUp(self):
        super(TestAssociationsTemplate, self).setUp()
        self.serializer = qos_specs_manage.AssociationsTemplate()

    def test_qos_associations_serializer(self):
        fixture = {
            "qos_associations": [
                {
                    "association_type": "volume_type",
                    "name": "type-4",
                    "id": "14d54d29-51a4-4046-9f6f-cf9800323563"
                },
                {
                    "association_type": "volume_type",
                    "name": "type-2",
                    "id": "3689ce83-308d-4ba1-8faf-7f1be04a282b"}
            ]
        }

        output = self.serializer.serialize(fixture)
        root = etree.XML(output)
        xmlutil.validate_schema(root, 'qos_associations')
        association_elems = root.findall("associations")
        self.assertEqual(2, len(association_elems))
        for i, association_elem in enumerate(association_elems):
            association_dict = fixture['qos_associations'][i]

            # check qos_spec attributes
            for key in ['name', 'id', 'association_type']:
                self.assertEqual(str(association_dict[key]),
                                 association_elem.get(key))


class TestQoSSpecsKeyDeserializer(test.TestCase):
    def setUp(self):
        super(TestQoSSpecsKeyDeserializer, self).setUp()
        self.deserializer = qos_specs_manage.QoSSpecsKeyDeserializer()

    def test_keys(self):
        self_request = """
<keys><xyz /><abc /></keys>"""
        request = self.deserializer.deserialize(self_request)
        expected = {
            "keys": ["xyz", "abc"]
        }
        self.assertEqual(expected, request['body'])

    def test_bad_format(self):
        self_request = """
<qos_specs><keys><xyz /><abc /></keys></qos_specs>"""
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.deserializer.deserialize, self_request)
