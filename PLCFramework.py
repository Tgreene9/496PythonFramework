#!/usr/bin/env python3
import subprocess
import logging
import nmap
import netifaces
import ipaddress
from pymodbus.client import ModbusTcpClient
from pymodbus.mei_message import ReadDeviceInformationRequest
from pymodbus.exceptions import ModbusException
from prettytable import PrettyTable
import socket
import numpy as np
import time

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ModbusScanner:
    def __init__(self):
        self.local_ip = self.get_local_ip()
        self.subnet_mask = self.get_subnet_mask()
        self.network = self.get_network()
        self.clients = []
        self.memory_map = {}
        logger.info(f"Hostname: {socket.gethostname()}")
        logger.info(f"Local IP: {self.local_ip}")
        logger.info(f"Subnet Mask: {self.subnet_mask}")

    def get_local_ip(self):
        for interface in netifaces.interfaces():
            addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
            if addr:
                for link in addr:
                    if link['addr'] != '127.0.0.1':
                        return link['addr']

    def get_subnet_mask(self):
        gws = netifaces.gateways()
        default_interface = gws['default'][netifaces.AF_INET][1]
        return netifaces.ifaddresses(default_interface)[netifaces.AF_INET][0]['netmask']

    def get_network(self):
        ip_interface = ipaddress.IPv4Interface(f'{self.local_ip}/{self.subnet_mask}')
        return ip_interface.network

    def connect_scan(self):
        nm = nmap.PortScanner()
        nm.scan(hosts=str(self.network), arguments='-p 502')
        clients_with_port_502_open = [host for host in nm.all_hosts() if nm[host].has_tcp(502) and nm[host]['tcp'][502]['state'] == 'open']
        return clients_with_port_502_open

    def read_device_identification(self, ip):
        client = ModbusTcpClient(ip)
        client.connect()
        request = ReadDeviceInformationRequest(unit=1)
        result = client.execute(request)
        client.close()
        if result and result.function_code < 0x80:
            return result.information
        else:
            return None

    def read_modbus_memory(self, client, addresses=None):
        sections = {
            'coils': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_coils},
            'discrete_inputs': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_discrete_inputs},
            'holding_registers': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_holding_registers},
            'input_registers': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_input_registers}
        }
        memory_map = {}
        for section, config in sections.items():
            start_address = config['start_address']
            num_elements = config['num_elements']
            read_func = config['read_func']
            values = {}

            address_range = range(start_address, start_address + num_elements)
            if addresses is not None:
                address_range = [address for address in address_range if address in addresses]

            for address in address_range:
                try:
                    response = read_func(address, 1)
                    if not response.isError():
                        if section in ['coils', 'discrete_inputs']:
                            values[address] = response.bits[0]
                        else:
                            values[address] = response.registers[0]
                except ModbusException:
                    pass

            # Add the values for the section if no errors occurred
            if len(values) > 0:
                memory_map[section] = values

        return memory_map

    def modbus_scan(self):
        self.clients.clear()
        clients = self.connect_scan()
        for ip in clients:
            try:
                client = ModbusTcpClient(ip)
                client.connect()
                device_info = self.read_device_identification(ip)
                memory_map = None
                try:
                    memory_map = self.read_modbus_memory(client)
                    if memory_map:  # If there is a memory map, assume it's a server
                        self.clients.append((ip, device_info, "Server", memory_map))
                    else:
                        self.clients.append((ip, device_info, "Client", None))
                except:
                    self.clients.append((ip, device_info, "Client", None))
                finally:
                    client.close()
            except Exception as e:
                logger.exception(f"Failed to connect or read memory map for {ip}: {e}")
                self.clients.append((ip, None, None, None))

    def print_clients(self, re_read_memory=False):
        for i, client in enumerate(self.clients, 1):
            ip, device_info, role, memory_map = client
            if re_read_memory and role == "Server" and memory_map is not None:
                new_client = ModbusTcpClient(ip)
                new_client.connect()
                try:
                    valid_addresses = set(address for section in memory_map.values() for address in section.keys())
                    new_memory_map = self.read_modbus_memory(new_client, addresses=valid_addresses)
                    self.clients[i-1] = (ip, device_info, role, new_memory_map)
                except Exception as e:
                    logger.exception(f"Failed to re-read memory map for {ip}: {e}")
                finally:
                    new_client.close()
            logger.info(f"{i}. {ip} - Device Info: {device_info} - Role: {role}")

    def write_modbus_memory(self, client, section_name, address, value):
        sections = [
            ("Coil", client.write_coil),
            ("Holding Register", client.write_register),
        ]
        for valid_section_name, write_func in sections:
            if valid_section_name == section_name:
                try:
                    response = write_func(address, value)
                    if isinstance(response, ModbusException):
                        logger.exception(f"Failed to write to {section_name} at address {address}: {response}")
                        return False
                    else:
                        self.update_memory_map(client, section_name, address)
                        return True
                except ModbusException as e:
                    logger.exception(f"Failed to write to {section_name} at address {address}: {e}")
                    return False
        logger.error(f"Invalid section name: {section_name}")
        return False
    
    def update_memory_map(self, client, section_name, address):
        sections = {
            'coils': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_coils},
            'holding_registers': {'start_address': 0, 'num_elements': 100, 'read_func': client.read_holding_registers}
        }
        config = sections.get(section_name)
        if config is None:
            return
        read_func = config['read_func']
        try:
            response = read_func(address, 1)
            if not response.isError():
                if section_name == 'Coil':
                    self.memory_map[section_name][address] = response.bits[0]
                else:
                    self.memory_map[section_name][address] = response.registers[0]
        except ModbusException:
            pass

    
    def poll_device(self):
        self.print_clients()
        selected = input("Select a device (or 'back' to go back): ")
        if selected.lower() == 'back':
            return
        selected = int(selected) - 1
        if selected >= len(self.clients):
            print("Invalid device. Please try again.")
            return
        polling_rate = int(input("Enter polling rate in seconds: "))
        polling_amount = min(20, int(input("Enter amount of polls (max 20): ")))

        _, _, _, memory_map = self.clients[selected]
        if memory_map is None:
            print("This client doesn't have a memory map.")
            return
        client = ModbusTcpClient(self.clients[selected][0])
        client.connect()

        # Initialize table with initial memory map values
        table = {}
        for section_name, section in memory_map.items():
            table[section_name] = np.zeros((len(section), polling_amount + 2), dtype=int)
            for i, (address, value) in enumerate(section.items()):
                table[section_name][i, 0] = address
                table[section_name][i, 1] = value

        valid_addresses = set(address for section in memory_map.values() for address in section.keys())

        # Poll the device and update the table
        for poll_num in range(polling_amount):
            time.sleep(polling_rate)
            new_memory_map = self.read_modbus_memory(client, addresses=valid_addresses)
            for section_name in table:
                new_section = new_memory_map.get(section_name, {})
                for i, address in enumerate(table[section_name][:, 0]):
                    table[section_name][i, poll_num + 2] = new_section.get(address, 0)

        client.close()

        # Print the table
        for section_name, section_table in table.items():
            ptable = PrettyTable()
            ptable.title = section_name
            ptable.field_names = ["Memory Address", "Initial Value"] + [f"{i+1}st Poll Value" for i in range(polling_amount)]
            for row in section_table:
                ptable.add_row(row)
            print(ptable)

    def searchsploit(self, vendor_name):
        try:
            result = subprocess.run(['searchsploit', vendor_name], capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            print(f"An error occurred while running searchsploit: {e}")
            return None

    def run(self):
        while True:
            print("\n")
            print("1. Enumerate network")
            if self.clients:
                print("2. Read device memory map")
                print("3. Write to device memory map")
                print("4. Poll device and display results")
                print("5. Searchsploit Device")
                print("6. Exit")
            choice = input("Choose an option: ")
            if choice == '1':
                self.modbus_scan()
                self.print_clients()
            elif choice == '2' and self.clients:
                self.print_clients(re_read_memory=True)
                selected = input("Select a device (or 'back' to go back): ")
                if selected.lower() == 'back':
                    continue
                selected = int(selected) - 1
                if selected < len(self.clients):
                    _, _, _, memory_map = self.clients[selected]
                    if memory_map is None:
                        logger.info("This client doesn't have a memory map.")
                    else:
                        for section_name, section in memory_map.items():
                            logger.info(f"\n{section_name}:\n{'-'*40}")
                            for address, value in section.items():
                                logger.info(f'{section_name.capitalize()} Address {address}: {value}')
        
            elif choice == '3' and self.clients:
                self.print_clients()
                selected = input("Select a device (or 'back' to go back): ")
                if selected.lower() == 'back':
                    continue
                selected = int(selected) - 1
                if selected >= len(self.clients):
                    print("Invalid device. Please try again.")
                    continue
                client_tuple = self.clients[selected]
                client = ModbusTcpClient(client_tuple[0])
                client.connect()
                section_name = input("Enter section name (Coil, Holding Register): ")
                try:
                    address = int(input("Enter address: "))
                    if section_name == "Coil":
                        value = int(input("Enter value (0 or 1 for Coil): "))
                        if value not in [0, 1]:
                            raise ValueError
                    else:  # Holding Register
                        value = int(input("Enter value (0-65535 for Holding Register): "))
                        if value < 0 or value > 65535:
                            raise ValueError
                except ValueError:
                    print("Invalid address or value. Please try again.")
                    continue
                success = self.write_modbus_memory(client, section_name, address, value)
                if success:
                    print(f"Successfully wrote to {section_name} at address {address}.")
                else:
                    print(f"Failed to write to {section_name} at address {address}.")
            elif choice == '4' and self.clients:
                self.poll_device()
            elif choice == '5' and self.clients:
                self.print_clients()
                selected = input("Select a device (or 'back' to go back): ")
                if selected.lower() == 'back':
                    continue
                selected = int(selected) - 1
                if selected >= len(self.clients):
                    print("Invalid device. Please try again.")
                    continue
                vendor_name = self.clients[selected][1].get(0)  # Get the vendor name from the device info
                if vendor_name:
                    vendor_name = vendor_name.decode()  # Convert bytes to string
                    searchsploit_results = self.searchsploit(vendor_name)
                    if searchsploit_results:
                        print(f"searchsploit results for {vendor_name}:\n{searchsploit_results}")
                    else:
                        print(f"No searchsploit results for {vendor_name}.")
                else:
                    print("This device does not have a vendor name.")
            elif choice == '6':
                break
            else:
                print("Invalid option. Please try again.")


if __name__ == '__main__':
    scanner = ModbusScanner()
    scanner.run()
