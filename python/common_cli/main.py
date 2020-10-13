# -*- mode: python; python-indent: 4 -*-
import ncs
import ncs.experimental
import _ncs
from ncs.dp import Action
import re


class RunAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        # if the your actions take more than 240 seconds, increase the action_set_timeout
        _ncs.dp.action_set_timeout(uinfo, 240)
        device = ''
        username = uinfo.username
        ctx = uinfo.context
        with ncs.maapi.single_read_trans(username, ctx) as trans:
            action_node = ncs.maagic.get_node(trans, kp)
            device_node = ncs.maagic.cd(action_node, '../')
            device = device_node.name

        device_type = get_device_type(device, username, ctx)
        if device_type == 'tailf-ned-cisco-ios':
            interfaces = get_ciscoios_interface(device, username, ctx)
        elif device_type == 'junos-rpc':
            interfaces = get_junos_interface(device, username, ctx)
        elif device_type == 'tailf-ned-cisco-ios-xr':
            interfaces = get_ciscoiosxr_interface(device, username, ctx)
        else:
            interfaces = get_test_interface(device, username, ctx)

        for interface in interfaces:
            # in future releases (>NSO 4.6) you will have to run create(key) as a normal
            # list entry
            outlist = output.interfaces.interface.create()
            outlist.type = interface['type']
            outlist.name = interface['name']
            outlist.ip_address = interface['ip-address']
            outlist.phys_address = interface['phys-address']
            outlist.oper_status = interface['oper-status']
            outlist.admin_status = interface['admin-status']


def interface_split(s):
    # split GigabitEthernet0 to GigabitEthernet 0
    # Not sure why the maxsplit=1 doesnt work with (\d)
    # Using join instead
    interface_parts = re.split(r'(\d+)', s, 1)
    interface_type = interface_parts[0]
    interface_name = ''.join(interface_parts[1:])
    # Drop all None interface, i.e remove empty
    return filter(None, [interface_type, interface_name])


def get_ciscoios_interface(device_name, username, context):
    print('new ios connection')
    with ncs.maapi.single_read_trans(username, context) as trans:
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.ncs__device[device_name]

        input = device.live_status.ios_stats__exec.show.get_input()
        input.args = 'ip interface brief'.split(' ')
        output = device.live_status.ios_stats__exec.show(input)

        if_data = output.result.split('\r')
        interfaces = []
        for line in if_data[2:-1]:
            interface = line.replace('administratively down', 'down').split()
            if line:
                interfaces.append({'type': str(interface_split(interface[0])[0]),
                                   'name': str(interface_split(interface[0])[1]),
                                   'admin-status': str(interface[4]),
                                   'ip-address': str(interface[1]),
                                   'phys-address': '-',
                                   'oper-status': str(interface[5])})
        return interfaces
        # There is a bug (at least in NSO 4.6.1) so checking if the value exists doesnt work.
        # so that is why Im using the live status exec version above
        #  interfaces = []
        #  for intf in device.live_status.ios_stats__interfaces:
        #     print('intf: ' + intf.type + ' ' + intf.name)
        #     ip_address = '-'
        #     phys_address_address = '-'
        #     if intf.ip_address':
        #         ip_address = intf.ip_address
        #     if intf.mac_address
        #         mac_address = intf.mac_address
        #     interfaces.append({'type':intf.type,
        #                        'name':intf.name,
        #                        'admin_status':intf.admin_status,
        #                        'ip_address':ip_address,
        #                        'mac_address':mac_address})


def get_ciscoiosxr_interface(device_name, username, context):
    with ncs.maapi.single_read_trans(username, context) as trans:
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.ncs__device[device_name]

        input = device.live_status.cisco_ios_xr_stats__exec.show.get_input()
        input.args = 'ip interface brief'.split(' ')
        output = device.live_status.cisco_ios_xr_stats__exec.show(input)

        if_data = output.result.split('\r')
        interfaces = []
        for line in if_data[5:-1]:
            interface = line.replace('Shutdown', 'down').split()
            interfaces.append({'int-type': str(interface_split(interface[0])[0]),
                               'int-name': str(interface_split(interface[0])[1]),
                               'admin-status': str(interface[2]).lower(),
                               'ip-address-and-prefix': str(interface[1]),
                               'mac': '-',
                               'oper-status': str(interface[3]).lower()})
        return interfaces


def get_junos_interface(device_name, username, context):
    print('new junos connection')
    with ncs.maapi.single_read_trans(username, context) as trans:
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.ncs__device[device_name]
        input = device.rpc.jrpc__rpc_get_interface_information.get_interface_information.get_input()
        input.brief.create()
        output = device.rpc.jrpc__rpc_get_interface_information.get_interface_information(input)
        interfaces = []
        for i in output.interface_information.physical_interface:
            for j in i.logical_interface:
                for k in j.address_family:
                    for l in k.interface_address:
                        interfaces.append({'type': str(i.link_level_type),
                                           'name': str(j.name),
                                           'admin-status': str(i.admin_status),
                                           'ip-address': str(l.ifa_local),
                                           'phys-address': '-',
                                           'oper-status': str(i.oper_status)})
        return interfaces


def get_test_interface(device_name, username, context):
    print("Test interfaces for: " + str(device_name))
    interfaces = []
    if 'c0' in device_name:
        interfaces = [
          {"type": "test", "name": "test0", "ip-address": "192.168.216.1",
           "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": False},
          {"type": "test", "name": "test1", "ip-address": "192.168.216.1",
           "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": False}
        ]
    else:
        interfaces = [
            {"type": "dummy", "name": "dummy0", "ip-address": "192.168.216.1",
             "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": False},
            {"type": "dummy", "name": "dummy1", "ip-address": "192.168.216.1",
             "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": False},
            {"type": "dummy", "name": "dummy2", "ip-address": "192.168.216.1",
             "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": True},
            {"type": "dummy", "name": "dummy3", "ip-address": "192.168.216.1",
             "phys-address": "sdf.sdsdf", "admin-status": True, "oper-status": False}
        ]
    return interfaces


def get_device_type(device_name, username, context):
    with ncs.maapi.single_read_trans(username, context) as trans:
        root = ncs.maagic.get_root(trans)
        device = root.ncs__devices.ncs__device[str(device_name)]
        device_type = 'Unknown'
        for module in device.module:
            if module.name == 'tailf-ned-cisco-ios':
                device_type = 'tailf-ned-cisco-ios'
            elif module.name == 'tailf-ned-cisco-ios-xr':
                device_type = 'tailf-ned-cisco-ios-xr'
            elif module.name == 'junos-rpc':
                device_type = 'junos-rpc'
        return device_type


class InterfacesHandler(object):
    def __init__(self):
        # Cache the interface list
        self.cache = {}

    def get_data(self, tctx, device_name):
        print("get new data from device: " + str(device_name))
        # Check if the interface list is already in the cache, if not populate it
        # I do this so I dont have to keep track of where we are in the list
        username = tctx.uinfo.username
        ctx = tctx.uinfo.context
        if device_name not in self.cache:
            device_type = get_device_type(device_name, username, ctx)
            if device_type == 'tailf-ned-cisco-ios':
                interfaces = get_ciscoios_interface(device_name, username, ctx)
            elif device_type == 'junos-rpc':
                interfaces = get_junos_interface(device_name, username, ctx)
            elif device_type == 'tailf-ned-cisco-ios-xr':
                interfaces = get_ciscoiosxr_interface(device_name, username, ctx)
            else:
                interfaces = get_test_interface(device_name, username, ctx)
            self.cache[device_name] = interfaces
            return interfaces
        else:
            return self.cache[device_name]

    def get_object(self, tctx, kp, args):
        print('get object kp: ' + str(kp) + ' args: ' + str(args))
        interface = next((o for o in self.get_data(tctx, args['device'])
                          if [o['type'], o['name']] == args['interface']), None)
        # Clear cache
        self.cache.pop(args['device'])
        return interface

    def get_next(self, tctx, kp, args, next):
        print("get next kp: " + str(kp) + ' args: ' + str(args) + ' next: ' + str(next))
        data = self.get_data(tctx, args['device'])
        if not data:
            return None
        if next >= len(data):
            # just clearing the cache so that the next connection gets new data.
            # dont want to keep track of the next counter
            self.cache.pop(args['device'])
            return None
        return data[next]

    def count(self, tctx, kp, args):
        if self.get_data(args['device']):
            return len(self.get_data(args['device']))
        else:
            return 0


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')
        self.register_action('get-interfaces-info', RunAction)

        def start_dcb_fun(state):
            dcb = ncs.experimental.DataCallbacks(self.log)
            dcb.register("/ncs:devices/ncs:device/norm-intf:interfaces/norm-intf:interface", InterfacesHandler())
            _ncs.dp.register_data_cb(state['ctx'], "getinterface", dcb)
            print('register show interface')
            return dcb

        def stop_dcb_fun(dcb):
            pass

        self.register_fun(start_dcb_fun, stop_dcb_fun)

    def teardown(self):
        self.log.info('Main FINISHED')
