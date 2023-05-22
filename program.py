import socket
import ipaddress
import netifaces
import pymodbus

class ModbusScanner:
    def __init__(self):
        self.local_ip = self.get_local_ip()
        self.subnet_mask = self.get_subnet_mask()
        self.network = self.get_network()
        self.clients = []

    def get_local_ip(self):
        return socket.gethostbyname(socket.gethostname())

    def get_subnet_mask(self):
        gws = netifaces.gateways()
        default_interface = gws['default'][netifaces.AF_INET][1]
        return netifaces.ifaddresses(default_interface)[netifaces.AF_INET][0]['netmask']

    def get_network(self):
        ip_interface = ipaddress.IPv4Interface(self.local_ip + '/' + self.subnet_mask)
        return ip_interface.network

    # WIP: Potentially adding threading to speed up the scan
    def connect_scan(self):
        clients_with_port_502_open = []
        for ip in self.network:
            port = 502
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((str(ip), port))
            if result == 0:
                clients_with_port_502_open.append(ip)
            sock.close()
        return clients_with_port_502_open

    def modbus_scan(self):
        clients_with_port_502_open = []
        clients = self.connect_scan()
        for ip in clients:
            try:
                device_info = self.read_device_identification(ip)
                clients_with_port_502_open.append((ip, device_info))
            except:
                clients_with_port_502_open.append((ip, None))
        self.clients = clients_with_port_502_open

    def read_device_identification(self, ip):
        client = pymodbus.ModbusTcpClient(ip)
        result = client.read_device_information()
        if result.function_code < 0x80:
            return result.information
        else:
            return None

    def read_modbus_memory(self, ip):
        client = pymodbus.ModbusTcpClient(ip)
        memory_map = {}
        for address in range(0, 20000):
            try:
                if 0 <= address < 10000:  # Discrete Outputs
                    result = client.read_coils(address, 1)
                else:  # Discrete Inputs
                    result = client.read_discrete_inputs(address - 10000, 1)
                if result.bits[0]:
                    memory_map[address] = True
            except pymodbus.ModbusIOException:
                pass
        client.close()
        return memory_map

    def print_clients(self):
        for i, client in enumerate(self.clients, 1):
            ip, device_info = client
            print(f"{i}. {ip} - Device Info: {device_info}")

    def scan(self):
        print("Scanning...")
        self.modbus_scan()
        print("Scan complete.")

    def run(self):
        while True:
            print("\n")
            print("1. Show local IP and subnet mask")
            print("2. Enumerate network")
            print("3. Read device memory map")
            print("4. Exit")
            choice = input("Choose an option: ")

            if choice == '1':
                print(f"Hostname: {socket.gethostname()}")
                print(f"Local IP: {self.local_ip}")
                print(f"Subnet Mask: {self.subnet_mask}")
            elif choice == '2':
                self.scan()
                self.print_clients()
            elif choice == '3':
                self.print_clients()
                selected = int(input("Select a device: ")) - 1
                if selected < len(self.clients):
                    memory_map = self.read_modbus_memory(self.clients[selected])
                    print(f"Memory Map for {self.clients[selected]}: {memory_map}")
                else:
                    print("Invalid selection.")
            elif choice == '4':
                break
            else:
                print("Invalid option.")


if __name__ == "__main__":
    scanner = ModbusScanner()
    scanner.run()
