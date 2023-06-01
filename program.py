import socket
import ipaddress
import netifaces
import time
from pymodbus.client import ModbusTcpClient
from pymodbus.mei_message import ReadDeviceInformationRequest
from pymodbus.file_message import ReadFileRecordRequest
import nmap

class ModbusScanner:
    def __init__(self):
        self.local_ip = self.get_local_ip()
        self.subnet_mask = self.get_subnet_mask()
        self.network = self.get_network()
        self.clients = []
        print(f"Hostname: {socket.gethostname()}")
        print(f"Local IP: {self.local_ip}")
        print(f"Subnet Mask: {self.subnet_mask}")

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
        ip_interface = ipaddress.IPv4Interface(self.local_ip + '/' + self.subnet_mask)
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

    def read_modbus_memory(self, ip):
        client = ModbusTcpClient(ip)
        client.connect()
        memory_map = {}
        for address in range(0, 20000):
            try:
                if 0 <= address < 10000:  # Discrete Outputs
                    result = client.read_coils(address, 1)
                else:  # Discrete Inputs
                    result = client.read_discrete_inputs(address - 10000, 1)
                if result.bits[0]:
                    memory_map[address] = True
            except:
                pass
        client.close()
        return memory_map

    def modbus_scan(self):
        self.clients.clear()
        clients = self.connect_scan()
        for ip in clients:
            try:
                device_info = self.read_device_identification(ip)
                memory_map = self.read_modbus_memory(ip)
                if memory_map:  # If we can read memory, it's a server
                    self.clients.append((ip, device_info, "Server", memory_map))
                else:  # If no memory, it's a client
                    self.clients.append((ip, device_info, "Client", None))
            except:
                self.clients.append((ip, None, None, None))

    def print_clients(self):
        for i, client in enumerate(self.clients, 1):
            ip, device_info, role, _ = client
            print(f"{i}. {ip} - Device Info: {device_info} - Role: {role}")

    def monitor_device(self, idx, polling_rate):
        _, _, _, memory_map = self.clients[idx]
        if not memory_map:
            print("Selected device has no memory map.")
            return
        try:
            while True:
                print(f"\nMemory Map for {self.clients[idx]}:")
                for address, value in memory_map.items():
                    print(f"Address: {address}, Value: {value}")
                time.sleep(polling_rate)
        except KeyboardInterrupt:
            print("Monitoring stopped.")

    def run(self):
        while True:
            print("\n")
            print("1. Enumerate network")
            print("2. Read device memory map")
            print("3. Monitor a device")
            print("4. Exit")
            choice = input("Choose an option: ")

            if choice == '1':
                self.modbus_scan()
                self.print_clients()
            elif choice == '2':
                self.print_clients()
                selected = int(input("Select a device: ")) - 1
                if selected < len(self.clients):
                    _, _, _, memory_map = self.clients[selected]
                    print(f"Memory Map for {self.clients[selected]}: {memory_map}")
                else:
                    print("Invalid selection.")
            elif choice == '3':
                self.print_clients()
                selected = int(input("Select a device: ")) - 1
                if selected < len(self.clients):
                    polling_rate = int(input("Enter polling rate (seconds): "))
                    self.monitor_device(selected, polling_rate)
                else:
                    print("Invalid selection.")
            elif choice == '4':
                break
            else:
                print("Invalid option.")

if __name__ == "__main__":
    scanner = ModbusScanner()
    scanner.run()
