from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from txgsm.tests.base import TxGSMBaseTestCase, LogCatcher
from txgsm.txgsm import TxGSMService, TxGSMProtocol

from mock import Mock


class TxGSMTestCase(TxGSMBaseTestCase):

    timeout = 1

    @inlineCallbacks
    def test_configure_modem(self):
        d = self.modem.configure_modem()
        yield self.assertExchange(['AT+CMGF=0'], ['OK'])
        yield self.assertExchange(['ATE0'], ['OK'])
        yield self.assertExchange(['AT+CMEE=1'], ['OK'])
        yield self.assertExchange(['AT+CSMS=1'], ['OK'])
        response = yield d
        self.assertEqual(response, ['OK', 'OK', 'OK', 'OK'])

    @inlineCallbacks
    def test_send_sms(self):
        d = self.modem.send_sms('+27761234567', 'hello world')
        yield self.assertCommands(['AT+CMGS=23'])
        self.reply('> ', delimiter='')
        [pdu_payload] = yield self.wait_for_next_commands()
        self.reply('OK')
        response = yield d
        self.assertEqual(response, ['> ', 'OK'])

    @inlineCallbacks
    def test_send_multipart_sms(self):
        d = self.modem.send_sms('+27761234567', '1' * 180)
        yield self.assertCommands(['AT+CMGS=153'])
        self.reply('> ', delimiter='')
        [pdu_payload] = yield self.wait_for_next_commands()
        self.reply('OK')
        yield self.assertCommands(['AT+CMGS=43'])
        self.reply('> ', delimiter='')
        [pdu_payload] = yield self.wait_for_next_commands()
        self.reply('OK')
        response = yield d
        self.assertEqual(response, ['> ', 'OK', '> ', 'OK'])

    @inlineCallbacks
    def test_ussd_session(self):
        d = self.modem.dial_ussd_code('*100#')
        yield self.assertExchange(
            input=['AT+CUSD=1,"*100#",15'],
            output=[
                'OK',
                ('+CUSD: 2,"Your balance is R48.70. Out of Airtime? '
                 'Dial *111# for Airtime Advance. T&Cs apply.",255')
            ])
        response = yield d
        self.assertEqual(response[0], 'OK')
        self.assertTrue(response[1].startswith('+CUSD: 2'))

    def test_dealing_with_unexpected_events(self):
        with LogCatcher() as catcher:
            self.reply('+FOO')
            [err_log] = catcher.logs
            self.assertTrue('Unsollicited response' in err_log['message'][0])
            self.assertTrue('+FOO' in err_log['message'][0])

    @inlineCallbacks
    def test_probe(self):
        d = self.modem.probe()
        yield self.assertExchange(['ATE0'], ['OK'])
        yield self.assertExchange(['AT+CIMI'], ['01234123412341234', 'OK'])
        yield self.assertExchange(['AT+CGMM'], ['Foo Bar Corp', 'OK'])
        response = yield d
        self.assertEqual(response,
                         ['OK',
                          '01234123412341234',
                          'OK',
                          'Foo Bar Corp',
                          'OK'
                          ])


class TxGSMServiceTestCase(TestCase):

    def setUp(self):
        self.mock_serial = Mock()
        self.service = TxGSMService('/dev/foo', bar='baz')
        self.service.serial_port_class = self.mock_serial

    @inlineCallbacks
    def test_start_service(self):
        d = self.service.onProtocol
        self.service.startService()
        protocol = yield d
        self.assertTrue(isinstance(protocol, TxGSMProtocol))
        self.assertTrue(self.mock_serial.called)
        [init_call] = self.mock_serial.call_args_list
        args, kwargs = init_call
        proto, device, reactor = args
        self.assertEqual(device, '/dev/foo')
        self.assertEqual(kwargs, {'bar': 'baz'})

    def test_stop_service(self):
        self.service.startService()
        self.service.port.loseConnection = Mock()
        self.service.stopService()
        self.assertTrue(self.service.port.loseConnection.called)
