from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Connect to the Modbus TCP server
client = ModbusTcpClient('localhost', port=502)

# Define the starting address and number of elements for each section
sections = {
    'coils': {'start_address': 0, 'num_elements': 100},
    'discrete_inputs': {'start_address': 0, 'num_elements': 100},
    'holding_registers': {'start_address': 0, 'num_elements': 100},
    'input_registers': {'start_address': 0, 'num_elements': 100}
}

# Read and print the values for each section
for section, config in sections.items():
    start_address = config['start_address']
    num_elements = config['num_elements']
    values = []

    for address in range(start_address, start_address + num_elements):
        try:
            if section == 'coils':
                response = client.read_coils(address, 1)
            elif section == 'discrete_inputs':
                response = client.read_discrete_inputs(address, 1)
            elif section == 'holding_registers':
                response = client.read_holding_registers(address, 1)
            elif section == 'input_registers':
                response = client.read_input_registers(address, 1)

            if not response.isError():
                if section in ['coils', 'discrete_inputs']:
                    values.append(response.bits[0])
                else:
                    values.append(response.registers[0])

        except ModbusException as e:
           pass

    # Print the values for the section if no errors occurred
    if len(values) > 0:
        print(f"{section.capitalize()}: {values}")

# Close the Modbus TCP client
client.close()
