# Import required libraries
import random
import logging
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server.async_io import StartTcpServer

# Enable logging (makes it easier to debug if something goes wrong)
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# Define your device identification
device_identification = ModbusDeviceIdentification()
device_identification.VendorName  = 'ModbusTagServer'
device_identification.ProductCode = 'pymodbus'
device_identification.VendorUrl   = 'Pymodbus.com'
device_identification.ProductName = 'pymodbus Server'
device_identification.ModelName   = 'pymodbus Server'
device_identification.MajorMinorRevision = '1.0'

# Define the Modbus registers
coils = ModbusSequentialDataBlock(0, [False] * 5)
discrete_inputs = ModbusSequentialDataBlock(1, [False] * 6)
holding_registers = ModbusSequentialDataBlock(1, [1234])
input_registers = ModbusSequentialDataBlock(1, [8888])

temperature_values = [random.randint(4, 15) for _ in range(7)]
holding_registers.setValues(1, temperature_values)
print("temperature_values:", temperature_values)


# Define the Modbus slave context
slave_context = ModbusSlaveContext(
    di=discrete_inputs,
    co=coils,
    hr=holding_registers,
    ir=input_registers
)

# Define the Modbus server context
server_context = ModbusServerContext(slaves=slave_context, single=True)

# Start the Modbus TCP server
StartTcpServer(context=server_context, address=("localhost", 502))


